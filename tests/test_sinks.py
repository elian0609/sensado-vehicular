"""Salidas de KI-1: archivo JSON Lines, reparto a varios sinks y tópicos MQTT."""

import json

import pytest

from semantic.annotator import annotate
from semantic.registry import registration_documents
from sinks.base import FanOutSink, JsonlFileSink, Ki1Sink
from sinks.topics import gateway_time_topic, topic_for


class SinkMemoria(Ki1Sink):
    def __init__(self):
        self.recibidos = []
        self.cerrado = False

    def emit(self, payload, topic, retain=False):
        self.recibidos.append((payload, topic, retain))

    def close(self):
        self.cerrado = True


class SinkRoto(Ki1Sink):
    def emit(self, payload, topic, retain=False):
        raise OSError("disco lleno")

    def close(self):
        raise OSError("no cierra")


def test_jsonl_escribe_una_linea_por_documento(tmp_path):
    ruta = tmp_path / "outbox.jsonl"
    sink = JsonlFileSink(str(ruta))
    for i in range(3):
        sink.emit(json.dumps({"n": i}), "t")
    sink.close()
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert [json.loads(linea)["n"] for linea in lineas] == [0, 1, 2]


def test_jsonl_agrega_al_final_sin_borrar_lo_anterior(tmp_path):
    ruta = tmp_path / "outbox.jsonl"
    for valor in ("a", "b"):
        sink = JsonlFileSink(str(ruta))
        sink.emit(json.dumps(valor), "t")
        sink.close()
    assert ruta.read_text(encoding="utf-8").splitlines() == ['"a"', '"b"']


def test_fanout_sigue_entregando_si_un_sink_falla():
    sano = SinkMemoria()
    reparto = FanOutSink(SinkRoto(), sano)
    reparto.emit("doc", "vehiculo/x", True)
    assert sano.recibidos == [("doc", "vehiculo/x", True)]
    reparto.close()
    assert sano.cerrado


def test_topicos_de_telemetria_y_registros(observation):
    assert topic_for(annotate(observation, clock_source="ntp")) == (
        "vehiculo/sensor/ppd42ns_01/observacion",
        False,
    )
    topicos = {d["@type"]: topic_for(d) for d in registration_documents()}
    assert topicos == {
        "sosa:Platform": ("vehiculo/plataforma/registro", True),
        "sosa:ObservableProperty": (
            "vehiculo/propiedad/low_pulse_occupancy_ratio/registro",
            True,
        ),
        "sosa:FeatureOfInterest": ("vehiculo/foi/ambient_air_at_device/registro", True),
        "sosa:Sensor": ("vehiculo/sensor/ppd42ns_01/registro", True),
    }


def test_topico_de_la_hora_del_gateway():
    assert gateway_time_topic() == "vehiculo/gateway/hora"


@pytest.mark.parametrize("malo", ["", "a/b", "a+b", "a#"])
def test_topico_rechaza_identificadores_no_validos(malo):
    with pytest.raises(ValueError):
        topic_for({"@type": "sosa:FeatureOfInterest", "feature_id": malo})


def test_topico_rechaza_tipos_desconocidos():
    with pytest.raises(ValueError):
        topic_for({"@type": "sosa:Actuation"})
