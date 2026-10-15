"""Semántica RDF del documento KI-1 v2, comprobada con un procesador JSON-LD estándar."""

import json

from pyld import jsonld

import config
from semantic.annotator import annotate
from semantic.registry import registration_documents
from tools.validate_jsonld import check

SOSA = "http://www.w3.org/ns/sosa/"


def _expandido(documento: dict) -> dict:
    (nodo,) = jsonld.expand(documento)
    return nodo


def test_id_expandido_es_iri_absoluta_bajo_id_base(observation):
    nodo = _expandido(annotate(observation, clock_source="gateway"))
    assert nodo["@id"] == (
        config.ID_BASE + "obs/ppd42ns_01/low_pulse_occupancy_ratio/20261008T161739Z"
    )


def test_feature_of_interest_es_iri_y_no_literal(observation):
    nodo = _expandido(annotate(observation, clock_source="gateway"))
    assert nodo[SOSA + "hasFeatureOfInterest"] == [
        {"@id": config.ID_BASE + "ambient_air_at_device"}
    ]


def test_sensor_y_propiedad_son_iris(observation):
    nodo = _expandido(annotate(observation, clock_source="gateway"))
    assert nodo[SOSA + "madeBySensor"] == [{"@id": config.ID_BASE + "ppd42ns_01"}]
    assert nodo[SOSA + "observedProperty"] == [
        {"@id": config.ID_BASE + "low_pulse_occupancy_ratio"}
    ]


def test_raw_no_genera_triples(observation):
    nquads = jsonld.to_rdf(
        annotate(observation, clock_source="gateway"), {"format": "application/n-quads"}
    )
    for clave in ("pulse_count", "low_time_seconds", "quality_flag", "clock_source", "gateway"):
        assert clave not in nquads
    assert len(nquads.strip().splitlines()) == 7  # tipo + 6 propiedades


def test_registro_foi_es_un_nodo_sosa_feature_of_interest():
    (foi,) = [d for d in registration_documents() if d["@type"] == "sosa:FeatureOfInterest"]
    nodo = _expandido(foi)
    assert nodo["@id"] == config.ID_BASE + "ambient_air_at_device"
    assert nodo["@type"] == [SOSA + "FeatureOfInterest"]


def test_validador_de_pc1_a_pc6_acepta_la_salida_v2(observation):
    for documento in [annotate(observation, clock_source="gateway"), *registration_documents()]:
        _, _, _, errores = check(json.dumps(documento))
        assert errores == [], (documento["@type"], errores)


def test_validador_rechaza_observacion_sin_id_y_con_foi_literal(observation):
    documento = annotate(observation, clock_source="gateway")
    del documento["@id"]
    documento["@context"] = {
        **documento["@context"],
        "feature_of_interest": "sosa:hasFeatureOfInterest",  # literal, como en v1
    }
    _, _, _, errores = check(json.dumps(documento))
    assert any("@id" in e for e in errores)
    assert any("PC6" in e for e in errores)
