"""
M1 para el Seeed Studio Grove DHT11 (temperatura y humedad relativa, bus digital de un hilo).

La temporización del protocolo (pulsos de 26-70 µs) la resuelve el driver del kernel `dht11`
(`dtoverlay=dht11,gpiopin=<GPIO>` en /boot/firmware/config.txt), que valida el checksum y expone
la medición en IIO: in_temp_input (m°C) e in_humidityrelative_input (m%RH). Este módulo solo lee
esos dos archivos: no necesita ninguna biblioteca de GPIO.

Leer in_temp_input dispara una medición y el driver la conserva 2 s, así que las dos propiedades
salen de la misma medición y comparten result_time. Un fallo del driver (EIO por checksum,
ETIMEDOUT) llega como OSError y se propaga: acquisition_loop (main.py) lo registra y vuelve a
intentarlo, sin generar observación.

raw.window_seconds es la duración real de la lectura (≈ 0,04 s), no el periodo de muestreo: la
medición es puntual y la app ubica cada observación en result_time − window_seconds / 2 (BL-53).
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from core.observation import Observation
from sensors.base import SensorModule


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DHT11Sensor(SensorModule):
    TEMPERATURE = ("air_temperature", "degree_celsius")
    HUMIDITY = ("relative_humidity", "percent_rh")
    # window_seconds debe ser > 0 (contrato KI-1 v2, exclusiveMinimum); resolución de 1 ms.
    MIN_WINDOW_SECONDS = 0.001

    def __init__(
        self,
        sensor_id: str,
        gpio_bcm: int,
        period_seconds: float,
        feature_of_interest: str,
        iio_dir: str | Path,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = _utc_now,
    ):
        """gpio_bcm solo se registra en raw (el pin lo fija el overlay). monotonic, sleep y now
        solo se sustituyen en pruebas. No accede al hardware: un DHT11 ausente falla en read()."""
        self.sensor_id = sensor_id
        self.gpio_bcm = gpio_bcm
        self.sample_window_seconds = period_seconds
        self.feature_of_interest = feature_of_interest
        self._iio_dir = Path(iio_dir)
        self._monotonic, self._sleep, self._now = monotonic, sleep, now

    def _leer(self, archivo: str) -> float:
        """Valor del driver en milésimas (m°C o m%RH), convertido a la unidad publicada."""
        return int((self._iio_dir / archivo).read_text().strip()) / 1000

    def read(self) -> list[Observation]:
        self._sleep(self.sample_window_seconds)

        inicio = self._monotonic()
        temperatura = self._leer("in_temp_input")  # dispara la medición
        humedad = self._leer("in_humidityrelative_input")  # misma medición (caché del driver)
        duracion = self._monotonic() - inicio
        result_time = self._now()

        raw = {
            "gpio_pin_bcm": self.gpio_bcm,
            "window_seconds": max(round(duracion, 3), self.MIN_WINDOW_SECONDS),
            "quality_flag": "ok",
        }
        return [
            Observation(
                sensor_id=self.sensor_id,
                observed_property=propiedad,
                value=valor,
                unit=unidad,
                result_time=result_time,
                feature_of_interest=self.feature_of_interest,
                raw=dict(raw),
            )
            for (propiedad, unidad), valor in (
                (self.TEMPERATURE, temperatura),
                (self.HUMIDITY, humedad),
            )
        ]
