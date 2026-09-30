"""
Salida del nodo edge hacia KI-1.

M2 entrega cada documento serializado a un Ki1Sink junto con su tópico y el
indicador retain (sinks/topics.py). La implementación concreta decide el
transporte, sin que M1 ni M2 cambien:
  - MqttSink (sinks/mqtt.py): transporte definido en la Fase 4.
  - JsonlFileSink: bandeja de salida en archivo, para pruebas sin broker.
"""
from abc import ABC, abstractmethod


class Ki1Sink(ABC):
    @abstractmethod
    def emit(self, payload: str, topic: str, retain: bool = False) -> None: ...

    def close(self) -> None: ...


class JsonlFileSink(Ki1Sink):
    """Un documento JSON-LD por línea. Ignora tópico y retain."""

    def __init__(self, path: str):
        self._f = open(path, "a", encoding="utf-8")

    def emit(self, payload: str, topic: str = "", retain: bool = False) -> None:
        self._f.write(payload + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()
