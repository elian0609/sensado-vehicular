"""
Salida del nodo edge hacia KI-1.

El transporte de KI-1 (MQTT) se define en la Fase 4. Mientras tanto, M2 escribe
a través de este contrato; en la Fase 4 se añade MqttSink implementando la
misma interfaz, sin tocar M1 ni M2.
"""
from abc import ABC, abstractmethod


class Ki1Sink(ABC):
    @abstractmethod
    def emit(self, payload: str) -> None: ...

    def close(self) -> None: ...


class JsonlFileSink(Ki1Sink):
    """Bandeja de salida provisional: un documento JSON-LD por línea."""

    def __init__(self, path: str):
        self._f = open(path, "a", encoding="utf-8")

    def emit(self, payload: str) -> None:
        self._f.write(payload + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()
