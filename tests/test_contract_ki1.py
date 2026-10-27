"""Toda la salida de KI-1 del nodo cumple el contrato v2 (MCS_BACKEND/contracts/v2).

- annotate() + serialize() valida contra ki1-observation;
- cada registro (plataforma, propiedades, FOI y sensores) valida contra sus esquemas;
- las fixtures v2 de KI-1 se comportan como se espera con las reglas del edge
  (identidad de ADR-002 y @context del edge);
- el @context publicado en docs/ es idéntico al del código y al del contrato.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest
from pyld import jsonld

import config
from semantic.annotator import annotate, serialize
from semantic.context import KI1_TELEMETRY_CONTEXT
from semantic.identity import observation_id
from semantic.registry import (
    FOI_CONTEXT,
    PLATFORM_CONTEXT,
    PROPERTY_CONTEXT,
    SENSOR_CONTEXT,
    registration_documents,
)
from sinks.topics import topic_for
from tests.conftest import CONTRACTS, contract_context, load_json, schema_errors

ROOT = Path(__file__).resolve().parents[1]

# Esquema del contrato y @context del edge con el que debe viajar cada mensaje.
EDGE_CONTEXTS = {
    "ki1-observation": KI1_TELEMETRY_CONTEXT,
    "ki1-registro-sensor": SENSOR_CONTEXT,
    "ki1-registro-platform": PLATFORM_CONTEXT,
    "ki1-registro-property": PROPERTY_CONTEXT,
    "ki1-registro-foi": FOI_CONTEXT,
}
# Campo que identifica la entidad en cada documento de registro (alias de @id).
ID_DEL_REGISTRO = {
    "sosa:Sensor": "sensor_id",
    "sosa:Platform": "vehicle_id",
    "sosa:ObservableProperty": "property_name",
    "sosa:FeatureOfInterest": "feature_id",
}
SCHEMA_BY_TYPE = {
    "sosa:Sensor": "ki1-registro-sensor",
    "sosa:Platform": "ki1-registro-platform",
    "sosa:ObservableProperty": "ki1-registro-property",
    "sosa:FeatureOfInterest": "ki1-registro-foi",
}
KI1_SCHEMAS = [*EDGE_CONTEXTS, "ki1-hora", "ki1-observation-raw"]


def _sin_red(url, options=None):
    raise jsonld.JsonLdError(f"contexto remoto no permitido: {url}", "loading document failed")


def edge_checks(schema_name: str, document: dict) -> list:
    """Esquema + reglas que el edge aplica al producir (identidad y @context)."""
    errores = schema_errors(schema_name, document)
    if schema_name not in EDGE_CONTEXTS or not isinstance(document, dict):
        return errores
    try:
        jsonld.to_rdf(document, {"documentLoader": _sin_red, "format": "application/n-quads"})
    except jsonld.JsonLdError as exc:
        errores.append(f"json-ld: {exc}")
    if document.get("@context") != EDGE_CONTEXTS[schema_name]:
        errores.append("@context distinto del que emite el edge")
    if schema_name == "ki1-observation" and "@id" in document:
        try:
            instante = datetime.fromisoformat(document["result_time"].replace("Z", "+00:00"))
            esperado = observation_id(
                document["sensor_id"], document["observed_property"], instante
            )
        except (KeyError, ValueError) as exc:
            errores.append(f"identidad: {exc}")
        else:
            if document["@id"] != esperado:
                errores.append(f"@id {document['@id']} ≠ {esperado}")
    return errores


# --- Salida real del nodo ---------------------------------------------------


def test_telemetria_emitida_valida_contra_ki1_observation_v2(observation):
    documento = json.loads(serialize(annotate(observation, clock_source="gateway")))
    assert edge_checks("ki1-observation", documento) == []


def test_telemetria_respeta_el_orden_de_claves_del_contrato(observation):
    documento = annotate(observation, clock_source="rtc")
    assert list(documento) == [
        "@context",
        "@id",
        "@type",
        "sensor_id",
        "observed_property",
        "value",
        "unit",
        "result_time",
        "feature_of_interest",
        "raw",
    ]


def test_telemetria_coincide_con_la_fixture_real_del_contrato(observation):
    fixture = load_json(CONTRACTS / "fixtures/ki1-observation/valid/telemetria-real-20261008.json")
    assert annotate(observation, clock_source="gateway") == fixture


def test_se_emite_un_registro_por_entidad_configurada_y_cada_uno_valida():
    documentos = registration_documents()
    tipos = [d["@type"] for d in documentos]
    assert set(tipos) == set(SCHEMA_BY_TYPE)
    assert tipos.count("sosa:Platform") == 1
    assert tipos.count("sosa:ObservableProperty") == len(config.OBSERVED_PROPERTIES)
    assert tipos.count("sosa:FeatureOfInterest") == len(config.FEATURES_OF_INTEREST)
    assert tipos.count("sosa:Sensor") == len(config.SENSOR_METADATA)
    for documento in documentos:
        esquema = SCHEMA_BY_TYPE[documento["@type"]]
        recibido = json.loads(serialize(documento))
        assert edge_checks(esquema, recibido) == [], documento["@type"]


def test_los_registros_coinciden_con_las_fixtures_del_contrato():
    # Por (tipo, identificador propio): con varios sensores o propiedades hay varios por tipo.
    por_entidad = {
        (d["@type"], d[ID_DEL_REGISTRO[d["@type"]]]): d for d in registration_documents()
    }
    fixtures = {
        ("sosa:Sensor", "ppd42ns_01"): "ki1-registro-sensor/valid/sensor-ppd42ns-01.json",
        ("sosa:Platform", "moto_01"): "ki1-registro-platform/valid/plataforma-moto-01.json",
        (
            "sosa:ObservableProperty",
            "low_pulse_occupancy_ratio",
        ): "ki1-registro-property/valid/propiedad-lpo.json",
        (
            "sosa:FeatureOfInterest",
            "ambient_air_at_device",
        ): "ki1-registro-foi/valid/foi-aire-ambiente.json",
    }
    for entidad, ruta in fixtures.items():
        assert por_entidad[entidad] == load_json(CONTRACTS / "fixtures" / ruta), entidad


def test_registro_foi_se_publica_retenido_en_su_topico():
    (foi,) = [d for d in registration_documents() if d["@type"] == "sosa:FeatureOfInterest"]
    assert topic_for(foi) == ("vehiculo/foi/ambient_air_at_device/registro", True)


# --- Fixtures del contrato ----------------------------------------------------


def _casos():
    for esquema in KI1_SCHEMAS:
        for tipo in ("valid", "invalid"):
            for ruta in sorted((CONTRACTS / "fixtures" / esquema / tipo).glob("*.json")):
                yield pytest.param(esquema, tipo, ruta, id=f"{esquema}/{tipo}/{ruta.stem}")


@pytest.mark.parametrize(("esquema", "tipo", "ruta"), list(_casos()))
def test_fixtures_v2_de_ki1_se_comportan_como_se_espera(esquema, tipo, ruta):
    errores = edge_checks(esquema, load_json(ruta))
    if tipo == "valid":
        assert errores == []
    else:
        assert errores, "la fixture inválida superó todas las comprobaciones"


# --- @context publicado -------------------------------------------------------


def test_contexto_del_codigo_es_el_del_contrato_v2():
    assert KI1_TELEMETRY_CONTEXT == contract_context("ki1-observation")
    assert SENSOR_CONTEXT == contract_context("ki1-registro-sensor")
    assert PLATFORM_CONTEXT == contract_context("ki1-registro-platform")
    assert PROPERTY_CONTEXT == contract_context("ki1-registro-property")
    assert FOI_CONTEXT == contract_context("ki1-registro-foi")


def test_contexto_publicado_en_docs_es_identico_al_del_codigo():
    publicado = load_json(ROOT / "docs" / "context" / "ki1.jsonld")["@context"]
    assert publicado == KI1_TELEMETRY_CONTEXT


def test_vocabulario_publicado_incluye_feature_kind():
    ttl = (ROOT / "docs" / "vocab.ttl").read_text(encoding="utf-8")
    html = (ROOT / "docs" / "vocab.html").read_text(encoding="utf-8")
    assert "proy:featureKind a owl:DatatypeProperty" in ttl
    assert "rdfs:domain sosa:FeatureOfInterest" in ttl
    assert 'id="featureKind"' in html


def test_ids_del_proyecto_siguen_siendo_constantes_del_contrato():
    assert config.ID_BASE == contract_context("ki1-observation")["@base"]
