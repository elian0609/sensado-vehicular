"""Vectores compartidos de identidad (MCS_BACKEND/contracts/v2/vectors/identity.json).

El backend aplica la misma regla de ADR-002 (services/identity.py) con los mismos vectores:
si ambos pasan, el @id que emite el edge es el que el backend recalcula y acepta.
"""

import json
from datetime import datetime

import pytest

import config
from semantic.identity import observation_id
from tests.conftest import CONTRACTS

VECTORES = json.loads((CONTRACTS / "vectors" / "identity.json").read_text(encoding="utf-8"))

# Fragmento del mensaje de ValueError de semantic/identity.py para cada código de error.
MENSAJES = {"sin_zona_horaria": "zona horaria", "segmento_invalido": "no válido"}


def test_los_vectores_usan_el_mismo_id_base():
    assert VECTORES["id_base"] == config.ID_BASE


@pytest.mark.parametrize("caso", VECTORES["cases"], ids=lambda c: c["name"])
def test_vector_de_identidad(caso):
    instante = datetime.fromisoformat(caso["result_time"])
    if "error" in caso:
        with pytest.raises(ValueError, match=MENSAJES[caso["error"]]):
            observation_id(caso["sensor_id"], caso["observed_property"], instante)
    else:
        relativo = observation_id(caso["sensor_id"], caso["observed_property"], instante)
        assert relativo == caso["expected_id"]
        assert config.ID_BASE + relativo == caso["expected_iri"]
