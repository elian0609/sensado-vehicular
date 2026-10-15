"""Robustez de M2: un fallo en una observación no detiene el nodo ni pierde la cola.

core/pipeline.py:
  - Pipeline.process(obs): anota, serializa, calcula el tópico y emite; si algo
    falla, escribe la observación cruda y el motivo en el archivo de errores.
  - run_loop(q, stop, pipeline, drain_timeout): consume la cola hasta que se
    pide parar y, al parar, vacía lo pendiente con un tiempo máximo.
"""

import json
import queue
import threading
import time

from core.pipeline import Pipeline, run_loop
from semantic.annotator import annotate as anotar_real
from sinks.base import JsonlFileSink, Ki1Sink
from tests.conftest import RESULT_TIME, make_observation


class SinkMemoria(Ki1Sink):
    def __init__(self):
        self.recibidos = []

    def emit(self, payload, topic, retain=False):
        self.recibidos.append((json.loads(payload), topic))


def _falla_si(sensor_id, etapa):
    def anotar(obs, clock_source=None):
        if obs.sensor_id == sensor_id and etapa == "annotate":
            raise RuntimeError("fallo de anotación simulado")
        return anotar_real(obs, clock_source=clock_source)

    return anotar


def _pipeline(tmp_path, **kw):
    sink = SinkMemoria()
    errores = JsonlFileSink(str(tmp_path / "outbox_ki1_errors.jsonl"))
    return sink, Pipeline(sink=sink, errors=errores, clock_source=lambda: "rtc", **kw)


def _errores(tmp_path):
    ruta = tmp_path / "outbox_ki1_errors.jsonl"
    return [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()]


def _tres_observaciones():
    return [
        make_observation(sensor_id="s1"),
        make_observation(sensor_id="s2"),
        make_observation(sensor_id="s3"),
    ]


def test_fallo_de_anotacion_no_detiene_el_bucle_y_registra_la_observacion(tmp_path):
    sink, pipeline = _pipeline(tmp_path, annotate=_falla_si("s2", "annotate"))
    q, stop = queue.Queue(), threading.Event()
    for obs in _tres_observaciones():
        q.put(obs)
    stop.set()  # pedir parada con la cola llena: debe vaciarla igualmente

    run_loop(q, stop, pipeline, drain_timeout=5)

    assert [doc["sensor_id"] for doc, _ in sink.recibidos] == ["s1", "s3"]
    (error,) = _errores(tmp_path)
    assert error["stage"] == "annotate"
    assert "fallo de anotación simulado" in error["error"]
    assert error["observation"]["sensor_id"] == "s2"
    assert error["observation"]["result_time"] == RESULT_TIME.isoformat()
    assert error["observation"]["raw"]["quality_flag"] == "ok"
    assert q.empty()


def test_fallo_de_serializacion_se_registra_y_sigue(tmp_path):
    def serializar(doc):
        if doc["sensor_id"] == "s1":
            raise TypeError("no serializable")
        return json.dumps(doc)

    sink, pipeline = _pipeline(tmp_path, serialize=serializar)
    resultados = [pipeline.process(o) for o in _tres_observaciones()]

    assert resultados == [False, True, True]
    assert [doc["sensor_id"] for doc, _ in sink.recibidos] == ["s2", "s3"]
    assert _errores(tmp_path)[0]["stage"] == "serialize"


def test_fallo_al_calcular_el_topico_se_registra_y_sigue(tmp_path):
    def topico(doc):
        if doc["sensor_id"] == "s3":
            raise ValueError("segmento de tópico no válido")
        return f"vehiculo/sensor/{doc['sensor_id']}/observacion", False

    sink, pipeline = _pipeline(tmp_path, topic_for=topico)
    resultados = [pipeline.process(o) for o in _tres_observaciones()]
    assert resultados == [True, True, False]
    assert _errores(tmp_path)[0]["stage"] == "topic"


def test_observacion_con_identificador_invalido_no_detiene_el_bucle(tmp_path):
    sink, pipeline = _pipeline(tmp_path)
    assert pipeline.process(make_observation(sensor_id="con/barra")) is False
    assert pipeline.process(make_observation()) is True
    assert _errores(tmp_path)[0]["observation"]["sensor_id"] == "con/barra"


def test_fallo_del_sink_no_detiene_el_bucle(tmp_path):
    class SinkRoto(Ki1Sink):
        def emit(self, payload, topic, retain=False):
            raise OSError("broker caído")

    errores = JsonlFileSink(str(tmp_path / "outbox_ki1_errors.jsonl"))
    pipeline = Pipeline(sink=SinkRoto(), errors=errores, clock_source=lambda: "rtc")
    assert pipeline.process(make_observation()) is False
    assert _errores(tmp_path)[0]["stage"] == "emit"


def test_el_bucle_sigue_vivo_hasta_que_se_pide_parar(tmp_path):
    sink, pipeline = _pipeline(tmp_path, annotate=_falla_si("s1", "annotate"))
    q, stop = queue.Queue(), threading.Event()
    hilo = threading.Thread(target=run_loop, args=(q, stop, pipeline, 5), daemon=True)
    hilo.start()
    for obs in _tres_observaciones():
        q.put(obs)
    limite = time.monotonic() + 5
    while len(sink.recibidos) < 2 and time.monotonic() < limite:
        time.sleep(0.01)
    assert hilo.is_alive()  # el fallo de s1 no terminó el bucle
    stop.set()
    hilo.join(timeout=5)
    assert not hilo.is_alive()
    assert len(sink.recibidos) == 2


def test_el_vaciado_al_parar_respeta_el_tiempo_maximo(tmp_path):
    class SinkLento(Ki1Sink):
        def __init__(self):
            self.n = 0

        def emit(self, payload, topic, retain=False):
            time.sleep(0.2)
            self.n += 1

    errores = JsonlFileSink(str(tmp_path / "outbox_ki1_errors.jsonl"))
    lento = SinkLento()
    pipeline = Pipeline(sink=lento, errors=errores, clock_source=lambda: "rtc")
    q, stop = queue.Queue(), threading.Event()
    for i in range(20):
        q.put(make_observation(sensor_id=f"s{i}"))
    stop.set()
    inicio = time.monotonic()
    pendientes = run_loop(q, stop, pipeline, drain_timeout=0.5)
    assert time.monotonic() - inicio < 1.5
    assert pendientes == 20 - lento.n > 0  # informa de lo que quedó sin procesar
