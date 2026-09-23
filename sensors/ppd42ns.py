"""
M1 para el Shinyei PPD42NS (variante de un solo canal de salida).

Mide el Low Pulse Occupancy (LPO): fracción de la ventana en que la salida del
sensor permanece en nivel bajo. El valor NO se convierte a µg/m³: esa
calibración es una transformación posterior, explícitamente fuera de esta fase.
"""
import threading
import time
from datetime import datetime, timezone
from typing import List

from core.observation import Observation
from sensors.base import SensorModule


class PPD42NSSensor(SensorModule):
    OBSERVED_PROPERTY = "low_pulse_occupancy_ratio"
    UNIT = "ratio_0_1"

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
            },
        )]

    def close(self) -> None:
        self._pin.close()
