"""
Salida del nodo edge hacia KI-1.

M2 entrega cada documento serializado a un Ki1Sink junto con su tópico y el
indicador retain (sinks/topics.py). La implementación concreta decide el
transporte, sin que M1 ni M2 cambien:
  - MqttSink (sinks/mqtt.py): transporte definido en la Fase 4.
  - JsonlFileSink: bandeja de salida en archivo, para pruebas sin broker.
  - FanOutSink: entrega cada documento a varios sinks (MQTT + archivo).
"""
import logging
import os
from abc import ABC, abstractmethod

log = logging.getLogger("edge_node.sink")


class Ki1Sink(ABC):
    @abstractmethod
    def emit(self, payload: str, topic: str, retain: bool = False) -> None: ...

    def close(self) -> None: ...


class JsonlFileSink(Ki1Sink):
    """
    Un documento JSON-LD por línea. Ignora tópico y retain.

    Cada línea se fuerza a la tarjeta SD con fsync: en el vehículo el nodo se
    apaga cortando la alimentación, y con solo flush() las últimas líneas
    quedaban en la caché del sistema y se perdían (o aparecían como bytes
    nulos) al volver a encender.
    """

    def __init__(self, path: str):
        self._f = open(path, "a", encoding="utf-8")
        # Persiste también la entrada del directorio si el archivo es nuevo.
        dir_fd = os.open(os.path.dirname(os.path.abspath(path)), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def emit(self, payload: str, topic: str = "", retain: bool = False) -> None:
        self._f.write(payload + "\n")
        self._f.flush()
        os.fsync(self._f.fileno())

    def close(self) -> None:
        self._f.close()


class FanOutSink(Ki1Sink):
    """
    Entrega cada documento a todos los sinks, en orden. Con MQTT + archivo, la
    bandeja registra lo que el nodo publicó y permite compararlo en la Fase 6
    con lo recibido por el gateway (pérdida de mensajes en KI-1).
    El fallo de un sink no impide la entrega a los demás.
    """

    def __init__(self, *sinks: Ki1Sink):
        self._sinks = sinks

    def emit(self, payload: str, topic: str, retain: bool = False) -> None:
        for s in self._sinks:
            try:
                s.emit(payload, topic, retain)
            except Exception:
                log.exception("Fallo al emitir en %s", type(s).__name__)

    def close(self) -> None:
        for s in self._sinks:
            try:
                s.close()
            except Exception:
                log.exception("Fallo al cerrar %s", type(s).__name__)
