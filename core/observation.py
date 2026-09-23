"""
Observation: resultado atómico producido por M1 (adquisición) y consumido
por M2 (anotación semántica). Es el contrato interno M1 -> M2 dentro de H2.

No contiene semántica ni formato de transporte: eso es responsabilidad
exclusiva de M2. Tampoco contiene latitud/longitud: H2 no tiene GPS; las
coordenadas las añade el gateway local (M3 sobre H3) tras cruzar KI-1.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass(frozen=True)
class Observation:
    sensor_id: str
    observed_property: str
    value: float
    unit: str
    result_time: datetime          # siempre con zona horaria UTC
    feature_of_interest: str
    raw: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.result_time.tzinfo is None:
            raise ValueError("result_time debe incluir zona horaria (UTC)")
