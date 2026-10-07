"""
M2 - Semantic Pipeline & Context Engine (sobre H2).

Etapas (Fase 3, algoritmo del motor semántico):
  1. Ingesta interna: recibe un Observation de M1 (sin cruzar ninguna KI).
  2. Captura contextual: result_time ya viene en UTC desde M1.
  3. Instanciación ontológica: asigna @type sosa:Observation e identificadores
     compactos.
  4. Serialización JSON-LD 1.1 con @context, lista para KI-1.
"""
import json
from typing import Any, Dict, Optional

from core.observation import Observation
from semantic.context import KI1_TELEMETRY_CONTEXT


def _iso_utc(dt) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def annotate(obs: Observation, clock_source: Optional[str] = None) -> Dict[str, Any]:
    """clock_source: de dónde venía la hora del nodo al medir ('ntp', 'gateway'
    o 'rtc', ver core/clock.py). Se guarda en raw, fuera de la expansión
    semántica, para poder evaluar la fiabilidad de cada result_time."""
    raw = obs.raw if clock_source is None else {**obs.raw, "clock_source": clock_source}
    return {
        "@context": KI1_TELEMETRY_CONTEXT,
        "@type": "sosa:Observation",
        "sensor_id": obs.sensor_id,
        "observed_property": obs.observed_property,
        "value": obs.value,
        "unit": obs.unit,
        "result_time": _iso_utc(obs.result_time),
        "feature_of_interest": obs.feature_of_interest,
        "raw": raw,
    }


def serialize(doc: Dict[str, Any]) -> str:
    """Serialización compacta (sin espacios): es la que se mide como payload."""
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
