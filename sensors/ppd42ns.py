"""
M1 para el Shinyei PPD42NS (variante de un solo canal de salida).

Mide el Low Pulse Occupancy (LPO): fracción de la ventana en que la salida del
sensor permanece en nivel bajo. El valor NO se convierte a µg/m³: esa
calibración es una transformación posterior, explícitamente fuera de esta fase.

raw.quality_flag:
  "ok"        medición válida.
  "stuck_low" la señal estuvo en bajo toda la ventana sin ningún pulso: el
              pin no tiene sensor (desconectado o cable suelto). LPO no válido.
"""
import logging
import threading
import time
from datetime import datetime, timezone
from typing import List

from core.observation import Observation
from sensors.base import SensorModule

log = logging.getLogger("edge_node.ppd42ns")


class PPD42NSSensor(SensorModule):
    OBSERVED_PROPERTY = "low_pulse_occupancy_ratio"
    UNIT = "ratio_0_1"
    # Fracción mínima de la ventana en bajo, sin pulsos, para declarar la señal
    # atascada. Con partículas reales el LPO observado no supera ~0.8.
    STUCK_LOW_MIN_RATIO = 0.99

    def __init__(self, sensor_id: str, gpio_bcm: int, window_seconds: float,
                 feature_of_interest: str):
        from gpiozero import DigitalInputDevice   # import tardío: permite simular

        self.sensor_id = sensor_id
        self.gpio_bcm = gpio_bcm
        self.sample_window_seconds = window_seconds
        self.feature_of_interest = feature_of_interest

        self._lock = threading.Lock()
        self._low_since = None
        self._low_total = 0.0
        self._pulses = 0

        # active_state=False: el pulso "activo" del PPD42NS es el nivel bajo.
        self._pin = DigitalInputDevice(gpio_bcm, pull_up=None, active_state=False)
        self._pin.when_activated = self._on_low
        self._pin.when_deactivated = self._on_high

    def _on_low(self):
        with self._lock:
            self._low_since = time.monotonic()

    def _on_high(self):
        with self._lock:
            if self._low_since is not None:
                self._low_total += time.monotonic() - self._low_since
                self._low_since = None
                self._pulses += 1

    def read(self) -> List[Observation]:
        with self._lock:
            self._low_total, self._pulses = 0.0, 0
            self._low_since = time.monotonic() if self._pin.is_active else None
            start = time.monotonic()

        time.sleep(self.sample_window_seconds)

        with self._lock:
            now = time.monotonic()
            low = self._low_total
            if self._low_since is not None:          # pulso aún abierto al cierre
                low += now - self._low_since
                self._low_since = now
            window = now - start
            pulses = self._pulses

        lpo = min(max(low / window, 0.0), 1.0)
        # Señal en bajo toda la ventana sin ningún flanco: no es una medición,
        # es el pin sin sensor (desconectado o cable suelto). La observación se
        # publica igual, por trazabilidad, pero marcada para descartarla.
        stuck_low = pulses == 0 and lpo >= self.STUCK_LOW_MIN_RATIO
        if stuck_low:
            log.warning("%s: señal en bajo toda la ventana (LPO=%.3f, 0 pulsos); "
                        "¿sensor desconectado?", self.sensor_id, lpo)
        return [Observation(
            sensor_id=self.sensor_id,
            observed_property=self.OBSERVED_PROPERTY,
            value=round(lpo, 6),
            unit=self.UNIT,
            result_time=datetime.now(timezone.utc),
            feature_of_interest=self.feature_of_interest,
            raw={
                "pulse_count": pulses,
                "low_time_seconds": round(low, 4),
                "window_seconds": round(window, 3),
                "gpio_pin_bcm": self.gpio_bcm,
                "quality_flag": "stuck_low" if stuck_low else "ok",
            },
        )]

    def close(self) -> None:
        self._pin.close()
