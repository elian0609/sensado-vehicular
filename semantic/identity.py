"""
Identidad de la observación (ADR-002 de MCS_BACKEND): ÚNICA implementación de la
regla en el nodo edge. Ningún otro módulo debe reconstruir el @id.

    @id = obs/{sensor_id}/{observed_property}/{result_time UTC en formato YYYYMMDDTHHMMSSZ}

El @id es relativo a @base (config.ID_BASE); al expandir el JSON-LD queda la IRI
absoluta, que el backend guarda como observation_id. El backend (M5) aplica la
MISMA regla: recalcula el @id a partir de la terna (sensor_id, observed_property,
result_time) y rechaza el nodo si no coincide; para nodos sin @id lo deriva. Por
eso cualquier cambio aquí es un cambio incompatible del contrato KI-1/KI-2 y
necesita un ADR nuevo.
"""

import re
from datetime import UTC, datetime

# Segmento válido de una IRI relativa sin codificación (contrato v2, idSegment).
_SEGMENTO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _segmento(nombre: str, valor: str) -> str:
    if not isinstance(valor, str) or not _SEGMENTO.match(valor):
        raise ValueError(f"{nombre} no válido para un @id: {valor!r}")
    return valor


def compact_utc(result_time: datetime) -> str:
    """result_time en UTC con precisión de segundo, formato básico YYYYMMDDTHHMMSSZ.

    Las fracciones de segundo se descartan, igual que en el result_time emitido
    (semantic/annotator.py), para que el @id y el result_time del documento
    describan el mismo instante.
    """
    if result_time.tzinfo is None or result_time.utcoffset() is None:
        raise ValueError("result_time debe incluir zona horaria")
    return result_time.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def observation_id(sensor_id: str, observed_property: str, result_time: datetime) -> str:
    """@id relativo de una observación según ADR-002."""
    return (
        f"obs/{_segmento('sensor_id', sensor_id)}"
        f"/{_segmento('observed_property', observed_property)}"
        f"/{compact_utc(result_time)}"
    )
