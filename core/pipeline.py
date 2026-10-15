"""
Bucle de M2 con aislamiento de fallos por observación.

Cada observación se anota, se serializa, se le asigna tópico y se emite a KI-1.
Si cualquiera de esas etapas falla, el error se registra con su contexto, la
observación cruda y el motivo se guardan en el archivo de errores
(config.ERRORS_PATH, JSON Lines con fsync) y el bucle sigue con la siguiente:
un fallo nunca termina el proceso ni descarta lo que queda en la cola.

Al pedir la parada (SIGTERM de systemd), run_loop vacía lo pendiente en la cola
durante un tiempo máximo (config.SHUTDOWN_DRAIN_SECONDS) antes de volver.
"""

import json
import logging
import queue
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime

from core.observation import Observation, observation_to_dict
from semantic.annotator import annotate as _annotate
from semantic.annotator import serialize as _serialize
from sinks.base import Ki1Sink
from sinks.topics import topic_for as _topic_for

log = logging.getLogger("edge_node.pipeline")


class Pipeline:
    def __init__(
        self,
        sink: Ki1Sink,
        errors: Ki1Sink,
        clock_source: Callable[[], str],
        annotate=_annotate,
        serialize=_serialize,
        topic_for=_topic_for,
    ):
        self._sink, self._errors, self._clock_source = sink, errors, clock_source
        self._annotate, self._serialize, self._topic_for = annotate, serialize, topic_for
        self.emitted = 0
        self.failed = 0

    def process(self, obs: Observation) -> bool:
        """Lleva una observación hasta KI-1. Devuelve False si falló (ya registrada)."""
        stage = "annotate"
        try:
            doc = self._annotate(obs, clock_source=self._clock_source())  # M2
            stage = "serialize"
            payload = self._serialize(doc)
            stage = "topic"
            topic, retain = self._topic_for(doc)
            stage = "emit"
            self._sink.emit(payload, topic, retain)  # KI-1
        except Exception as exc:
            self.failed += 1
            log.exception(
                "Fallo en la etapa %s de %s %s @ %s; se guarda en el archivo de errores",
                stage,
                obs.sensor_id,
                obs.observed_property,
                obs.result_time,
            )
            self._record_error(obs, stage, exc)
            return False
        self.emitted += 1
        log.info(
            "KI-1 <- %s %s=%s (%d bytes) -> %s",
            obs.sensor_id,
            obs.observed_property,
            obs.value,
            len(payload.encode()),
            topic,
        )
        return True

    def _record_error(self, obs: Observation, stage: str, exc: Exception) -> None:
        record = {
            "logged_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "stage": stage,
            "error": f"{type(exc).__name__}: {exc}",
            "observation": observation_to_dict(obs),
        }
        try:
            self._errors.emit(json.dumps(record, ensure_ascii=False, default=str), "", False)
        except Exception:
            log.exception("Tampoco se pudo escribir en el archivo de errores: %r", record)


def run_loop(
    q: "queue.Queue[Observation]",
    stop: threading.Event,
    pipeline: Pipeline,
    drain_timeout: float,
    max_emitted: int | None = None,
) -> int:
    """Procesa la cola hasta que se pide parar; luego vacía lo pendiente.

    Devuelve el número de observaciones que quedaron sin procesar en la cola
    porque se agotó drain_timeout (0 si se vació por completo).
    """
    while not stop.is_set():
        if max_emitted is not None and pipeline.emitted >= max_emitted:
            return q.qsize()
        try:
            obs = q.get(timeout=0.5)
        except queue.Empty:
            continue
        pipeline.process(obs)

    deadline = time.monotonic() + drain_timeout
    drained = 0
    while time.monotonic() < deadline:
        try:
            obs = q.get_nowait()
        except queue.Empty:
            break
        pipeline.process(obs)
        drained += 1
    pending = q.qsize()
    if drained:
        log.info("Parada: %d observaciones pendientes procesadas", drained)
    if pending:
        log.warning(
            "Parada: %d observaciones sin procesar tras %.1f s de vaciado", pending, drain_timeout
        )
    return pending
