"""
Hora del nodo edge (H2): de dónde viene y cómo se corrige.

Fuentes, de mejor a peor:
  ntp      sincronizada por internet (systemd-timesyncd).
  gateway  confirmada o corregida hace poco con la hora del teléfono, que la
           app publica en KI-1 (vehiculo/gateway/hora) al conectarse y cada
           10 min. Funciona sin internet.
  rtc      solo la del RTC DS1302 al arrancar; deriva ~1-2 s/día.

La hora importa por dos motivos: result_time es parte de la clave de la
Observación (DIV-2) y la app geolocaliza cada observación buscando su
result_time en la trayectoria GPS del teléfono (1 s de desfase ≈ 8 m a 30 km/h).
"""
import json
import logging
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional

import config

log = logging.getLogger("edge_node.clock")


def ntp_synchronized() -> bool:
    out = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                         capture_output=True, text=True)
    return out.stdout.strip() == "yes"


def _set_system_clock(dt: datetime) -> None:
    # Requiere CAP_SYS_TIME (deploy/systemd/edge-node.service)
    time.clock_settime(time.CLOCK_REALTIME, dt.timestamp())


def _write_rtc(dt: datetime) -> None:
    from tools.rtc_ds1302 import DS1302      # import tardío: GPIO solo al corregir
    rtc = DS1302(config.RTC_DS1302_GPIO_CLK, config.RTC_DS1302_GPIO_DAT,
                 config.RTC_DS1302_GPIO_RST)
    try:
        rtc.write(dt)
    finally:
        rtc.close()


class ClockSync:
    """Aplica la hora del gateway cuando no hay NTP y conoce la fuente actual."""

    def __init__(self,
                 ntp_synced: Callable[[], bool] = ntp_synchronized,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 set_clock: Callable[[datetime], None] = _set_system_clock,
                 write_rtc: Callable[[datetime], None] = _write_rtc,
                 monotonic: Callable[[], float] = time.monotonic):
        self._ntp_synced, self._now = ntp_synced, now
        self._set_clock, self._write_rtc = set_clock, write_rtc
        self._monotonic = monotonic
        self._last_gateway_check: Optional[float] = None
        self._lock = threading.Lock()

    def source(self) -> str:
        """Fuente de la hora en este momento: 'ntp', 'gateway' o 'rtc'."""
        if self._ntp_synced():
            return "ntp"
        with self._lock:
            last = self._last_gateway_check
        if last is not None and self._monotonic() - last <= config.CLOCK_GATEWAY_VALID_S:
            return "gateway"
        return "rtc"

    def on_gateway_time(self, payload: bytes) -> str:
        """Procesa un mensaje de vehiculo/gateway/hora. Devuelve la acción tomada."""
        try:
            phone = datetime.fromisoformat(json.loads(payload)["utc"])
            if phone.tzinfo is None:
                raise ValueError("hora sin zona horaria")
        except (ValueError, KeyError, TypeError) as e:
            log.warning("Hora del gateway no válida (%s): %r", e, payload[:80])
            return "invalida"
        if phone.year < config.CLOCK_MIN_VALID_YEAR:
            log.warning("Hora del gateway no plausible: %s", phone.isoformat())
            return "invalida"
        if self._ntp_synced():
            return "ignorada_ntp"            # NTP es mejor referencia que el teléfono

        offset = (phone - self._now()).total_seconds()
        if abs(offset) < config.CLOCK_SYNC_MIN_OFFSET_S:
            self._mark_checked()
            return "en_hora"
        if offset < -config.CLOCK_SYNC_MAX_BACKWARD_S:
            # Retroceder mucho repetiría result_time ya emitidos (clave DIV-2)
            log.warning("Hora del gateway %.1f s por detrás del nodo: no se retrocede "
                        "más de %d s", -offset, config.CLOCK_SYNC_MAX_BACKWARD_S)
            return "rechazada_atras"

        self._set_clock(phone)
        log.info("Hora corregida con el gateway: %+.1f s (ahora %s)", offset,
                 phone.isoformat(timespec="seconds"))
        try:
            self._write_rtc(phone)
        except Exception:
            log.exception("No se pudo actualizar el RTC DS1302")
        self._mark_checked()
        return "corregida"

    def _mark_checked(self) -> None:
        with self._lock:
            self._last_gateway_check = self._monotonic()
