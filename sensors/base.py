"""
Contrato de software de M1 (Sensor Data Acquisition Engine).

Cada sensor físico implementa esta interfaz una única vez. El orquestador no
conoce detalles de ningún sensor concreto: agregar uno nuevo es un archivo
nuevo en sensors/ y una línea en main.py.
"""

from abc import ABC, abstractmethod

from core.observation import Observation


class SensorModule(ABC):
    sensor_id: str
    sample_window_seconds: float  # ventana propia del sensor (según su datasheet)

    @abstractmethod
    def read(self) -> list[Observation]:
        """Bloquea durante una ventana de muestreo completa y devuelve las
        observaciones producidas en ella. Devuelve una lista porque un mismo
        dispositivo puede medir varias propiedades (p. ej. DHT11)."""

    def close(self) -> None:  # noqa: B027 (gancho opcional, no abstracto)
        """Libera recursos de hardware (GPIO). Opcional."""
