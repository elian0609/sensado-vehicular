"""Utilidades comunes de las pruebas: contratos v2 sincronizados desde MCS_BACKEND.

Las fixtures, los @context y los esquemas viven en tests/fixtures/contracts/ y se
copian con `MCS_BACKEND/contracts/tools/sync_fixtures.py sync --dest ...`; no se
editan a mano (test_fixtures_manifest.py lo comprueba).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from core.observation import Observation

CONTRACTS = Path(__file__).parent / "fixtures" / "contracts"
RESULT_TIME = datetime(2026, 10, 8, 16, 17, 39, tzinfo=timezone.utc)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _registry() -> Registry:
    recursos = []
    for ruta in (CONTRACTS / "schemas").glob("*.schema.json"):
        esquema = load_json(ruta)
        recursos.append((esquema["$id"], Resource.from_contents(esquema, DRAFT202012)))
    return Registry().with_resources(recursos)


_REGISTRY = _registry()


def validator(schema_name: str) -> Draft202012Validator:
    esquema = load_json(CONTRACTS / "schemas" / f"{schema_name}.schema.json")
    return Draft202012Validator(esquema, registry=_REGISTRY)


def schema_errors(schema_name: str, document) -> list:
    return [e.message for e in validator(schema_name).iter_errors(document)]


def contract_context(name: str) -> dict:
    return load_json(CONTRACTS / "context" / f"{name}.context.jsonld")["@context"]


def make_observation(**overrides) -> Observation:
    campos = {
        "sensor_id": "ppd42ns_01",
        "observed_property": "low_pulse_occupancy_ratio",
        "value": 0.133345,
        "unit": "ratio_0_1",
        "result_time": RESULT_TIME,
        "feature_of_interest": "ambient_air_at_device",
        "raw": {
            "pulse_count": 38,
            "low_time_seconds": 4.0004,
            "window_seconds": 30.0,
            "gpio_pin_bcm": 4,
            "quality_flag": "ok",
        },
    }
    campos.update(overrides)
    return Observation(**campos)


@pytest.fixture
def observation() -> Observation:
    return make_observation()
