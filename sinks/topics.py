"""
Jerarquía de tópicos MQTT de KI-1 (Fase 4).

  Telemetría:  {raíz}/sensor/{sensor_id}/observacion           (sin retain)
  Registro:    {raíz}/plataforma/registro                      (retain)
               {raíz}/propiedad/{property_name}/registro       (retain)
               {raíz}/sensor/{sensor_id}/registro              (retain)

Los metadatos de registro se publican con retain para que un gateway que se
suscriba después del arranque del nodo edge los reciba igualmente.
"""
from typing import Any, Dict, Tuple

import config

_INVALID = set("+#/\x00")


def _segment(value: str) -> str:
    if not value or _INVALID & set(value):
        raise ValueError(f"Identificador no válido como segmento de tópico: {value!r}")
    return value


def topic_for(doc: Dict[str, Any]) -> Tuple[str, bool]:
    """Devuelve (tópico, retain) para un documento JSON-LD del DIV-3."""
    root, kind = config.MQTT_TOPIC_ROOT, doc.get("@type")
    if kind == "sosa:Observation":
        return f"{root}/sensor/{_segment(doc['sensor_id'])}/observacion", False
    if kind == "sosa:Sensor":
        return f"{root}/sensor/{_segment(doc['sensor_id'])}/registro", True
    if kind == "sosa:Platform":
        return f"{root}/plataforma/registro", True
    if kind == "sosa:ObservableProperty":
        return f"{root}/propiedad/{_segment(doc['property_name'])}/registro", True
    raise ValueError(f"Tipo de documento sin tópico asignado: {kind!r}")
