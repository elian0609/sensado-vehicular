"""
Reloj de tiempo real DS1302 para el nodo edge (H2).

La Raspberry Pi no tiene reloj propio: si arranca sin internet, su hora es la
del último apagado y los result_time de las observaciones serían falsos. El
DS1302, con su pila, sigue contando con la Pi apagada.

El DS1302 no usa I2C sino una interfaz de 3 hilos (CLK, DAT, RST/CE) que no
tiene controlador en Raspberry Pi OS; este módulo la implementa por GPIO con
lgpio. El RTC guarda la hora en UTC.

Uso (como root, desde los servicios de deploy/systemd/):
  python3 -m tools.rtc_ds1302 leer      # muestra la hora del RTC
  python3 -m tools.rtc_ds1302 guardar   # RTC <- hora del sistema (solo si NTP está sincronizado)
  python3 -m tools.rtc_ds1302 ajustar   # sistema <- RTC (solo si NTP NO está sincronizado)
  python3 -m tools.rtc_ds1302 guardar --forzar   # escribe aunque no haya NTP (puesta en hora manual)
"""
import argparse
import sys
import time
from datetime import datetime, timezone
from typing import List, Optional

import config
from core.clock import ntp_synchronized

# Comandos de ráfaga (burst) del DS1302: 7 registros de reloj + control.
_CLOCK_BURST_READ = 0xBF
_CLOCK_BURST_WRITE = 0xBE
_CONTROL_WRITE = 0x8E           # bit 7 = WP (protección contra escritura)
_HALF_PERIOD_S = 2e-6           # muy por encima del mínimo del DS1302 a 3,3 V

# Fechas anteriores no pueden ser una hora válida para este proyecto.
MIN_VALID_YEAR = 2026


def _bcd(value: int) -> int:
    return (value // 10) << 4 | (value % 10)


def _unbcd(value: int) -> int:
    return (value >> 4) * 10 + (value & 0x0F)


def encode_clock(dt: datetime) -> List[int]:
    """Registros 0-6 del DS1302 para una hora UTC (24 h, CH = 0: reloj en marcha)."""
    dt = dt.astimezone(timezone.utc)
    return [
        _bcd(dt.second),                # bit 7 = CH (clock halt) en 0
        _bcd(dt.minute),
        _bcd(dt.hour),                  # bit 7 = 0: modo 24 h
        _bcd(dt.day),
        _bcd(dt.month),
        _bcd(dt.isoweekday()),          # 1-7
        _bcd(dt.year - 2000),
    ]


def decode_clock(regs: List[int]) -> Optional[datetime]:
    """Hora UTC de los registros 0-6, o None si el reloj está detenido o no es válida."""
    if regs[0] & 0x80:                  # CH: oscilador detenido (nunca puesto en hora)
        return None
    if regs[2] & 0x80:                  # modo 12 h: este módulo siempre escribe 24 h
        return None
    try:
        dt = datetime(2000 + _unbcd(regs[6]), _unbcd(regs[4] & 0x1F), _unbcd(regs[3] & 0x3F),
                      _unbcd(regs[2] & 0x3F), _unbcd(regs[1] & 0x7F), _unbcd(regs[0] & 0x7F),
                      tzinfo=timezone.utc)
    except ValueError:                  # fecha imposible (p. ej. todo ceros)
        return None
    return dt if dt.year >= MIN_VALID_YEAR else None


class DS1302:
    def __init__(self, clk: int, dat: int, rst: int):
        import lgpio                    # import tardío: permite probar sin hardware
        self._lg = lgpio
        self._h = self._open_chip()
        self.clk, self.dat, self.rst = clk, dat, rst
        for pin in (clk, rst):
            lgpio.gpio_claim_output(self._h, pin, 0)
        lgpio.gpio_claim_input(self._h, dat)

    def _open_chip(self) -> int:
        """gpiochip de los GPIO del conector (su número varía entre kernels)."""
        for chip in range(8):
            try:
                h = self._lg.gpiochip_open(chip)
            except Exception:
                continue
            if "pinctrl-bcm" in self._lg.gpio_get_chip_info(h)[3]:
                return h
            self._lg.gpiochip_close(h)
        raise RuntimeError("No se encontró el gpiochip de los GPIO del conector")

    def _tick(self):
        time.sleep(_HALF_PERIOD_S)
        self._lg.gpio_write(self._h, self.clk, 1)
        time.sleep(_HALF_PERIOD_S)
        self._lg.gpio_write(self._h, self.clk, 0)

    def _write_byte(self, byte: int):
        self._lg.gpio_claim_output(self._h, self.dat, 0)
        for i in range(8):              # LSB primero; el DS1302 lee en el flanco de subida
            self._lg.gpio_write(self._h, self.dat, (byte >> i) & 1)
            self._tick()

    def _read_byte(self) -> int:
        self._lg.gpio_claim_input(self._h, self.dat)
        byte = 0
        for i in range(8):              # el DS1302 pone cada bit tras el flanco de bajada
            byte |= self._lg.gpio_read(self._h, self.dat) << i
            self._tick()
        return byte

    def _transaction(self, command: int, data: Optional[List[int]] = None, read: int = 0):
        self._lg.gpio_write(self._h, self.clk, 0)
        self._lg.gpio_write(self._h, self.rst, 1)
        time.sleep(4e-6)
        try:
            self._write_byte(command)
            for b in data or []:
                self._write_byte(b)
            return [self._read_byte() for _ in range(read)]
        finally:
            self._lg.gpio_write(self._h, self.rst, 0)
            self._lg.gpio_claim_input(self._h, self.dat)
            time.sleep(4e-6)

    def read_raw(self) -> List[int]:
        return self._transaction(_CLOCK_BURST_READ, read=8)[:7]

    def read(self) -> Optional[datetime]:
        return decode_clock(self.read_raw())

    def write(self, dt: datetime):
        self._transaction(_CONTROL_WRITE, [0x00])                       # quita WP
        self._transaction(_CLOCK_BURST_WRITE, encode_clock(dt) + [0x80])  # hora + WP

    def close(self):
        self._lg.gpiochip_close(self._h)


def set_system_clock(dt: datetime):
    time.clock_settime(time.CLOCK_REALTIME, dt.timestamp())


def main() -> int:
    ap = argparse.ArgumentParser(description="RTC DS1302 del nodo edge")
    ap.add_argument("accion", choices=["leer", "guardar", "ajustar"])
    ap.add_argument("--forzar", action="store_true",
                    help="con 'guardar': escribe aunque NTP no esté sincronizado")
    args = ap.parse_args()

    rtc = DS1302(config.RTC_DS1302_GPIO_CLK, config.RTC_DS1302_GPIO_DAT,
                 config.RTC_DS1302_GPIO_RST)
    try:
        if args.accion == "leer":
            raw = rtc.read_raw()
            dt = decode_clock(raw)
            print("registros:", " ".join(f"{b:02x}" for b in raw))
            print("RTC:", dt.isoformat() if dt else "sin hora válida")
            print("sistema:", datetime.now(timezone.utc).isoformat(timespec="seconds"))
            return 0 if dt else 1

        if args.accion == "guardar":
            if not (args.forzar or ntp_synchronized()):
                print("NTP no sincronizado: no se escribe el RTC (él es la referencia)")
                return 0
            now = datetime.now(timezone.utc)
            rtc.write(now)
            check = rtc.read()
            if check is None or abs((check - now).total_seconds()) > 2:
                print(f"ERROR: verificación fallida (leído: {check})", file=sys.stderr)
                return 1
            print("RTC <- sistema:", check.isoformat())
            return 0

        # ajustar: al arrancar sin internet, la hora del sistema viene del RTC
        if ntp_synchronized():
            print("NTP sincronizado: no se toca la hora del sistema")
            return 0
        dt = rtc.read()
        if dt is None:
            print("ERROR: el RTC no tiene una hora válida; la hora del sistema "
                  "no es fiable hasta sincronizar por NTP", file=sys.stderr)
            return 1
        set_system_clock(dt)
        print("sistema <- RTC:", dt.isoformat())
        return 0
    finally:
        rtc.close()


if __name__ == "__main__":
    sys.exit(main())
