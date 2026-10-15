"""
Observation: resultado atómico producido por M1 (adquisición) y consumido
por M2 (anotación semántica). Es el contrato interno M1 -> M2 dentro de H2.

No contiene semántica ni formato de transporte: eso es responsabilidad
exclusiva de M2. Tampoco contiene latitud/longitud: H2 no tiene GPS; las
coordenadas las añade el gateway local (M3 sobre H3) tras cruzar KI-1.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Observation:
    sensor_id: str
    observed_property: str
    value: float
    unit: str
    result_time: datetime  # siempre con zona horaria UTC
    feature_of_interest: str
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.result_time.tzinfo is None:
            raise ValueError("result_time debe incluir zona horaria (UTC)")


def observation_to_dict(obs: Observation) -> dict[str, Any]:
    """Observación cruda serializable (archivo de errores): mismos nombres de campo,
    result_time en ISO 8601 con zona horaria."""
    return {
        "sensor_id": obs.sensor_id,
        "observed_property": obs.observed_property,
        "value": obs.value,
        "unit": obs.unit,
        "result_time": obs.result_time.isoformat(),
        "feature_of_interest": obs.feature_of_interest,
        "raw": obs.raw,
    }
