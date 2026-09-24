"""
Metadatos de registro (DIV-3): documentos de baja frecuencia que el nodo edge
emite al iniciar, fuera de la ruta crítica de telemetría.

El documento del sensor incluye sosa:isHostedBy, que materializa la relación
'monta' (Plataforma -> Sensor) del DIV-2 y completa la PC2 ("¿en qué
plataforma se encuentra alojado el sensor?") sin repetir el vehículo en cada
observación.
"""
from typing import Any, Dict, List

import config
from semantic.context import SOSA, XSD

_BASE = {"@base": config.ID_BASE, "sosa": SOSA, "xsd": XSD, "proy": config.VOCAB_NS}

SENSOR_CONTEXT = {
    **_BASE,
    "sensor_id": "@id",
    "hosted_by": {"@id": "sosa:isHostedBy", "@type": "@id"},
    "sensor_model": "proy:sensorModel",
    "sensor_type": "proy:sensorType",
    "calibration_params": {"@id": "proy:calibrationParams", "@type": "@json"},
    "install_date": {"@id": "proy:installDate", "@type": "xsd:date"},
    "status": "proy:status",
}

PLATFORM_CONTEXT = {
    **_BASE,
    "vehicle_id": "@id",
    "vehicle_type": "proy:vehicleType",
    "route_label": "proy:routeLabel",
    "registration_date": {"@id": "proy:registrationDate", "@type": "xsd:date"},
}

PROPERTY_CONTEXT = {
    **_BASE,
    "property_name": "@id",
    "unit": "proy:defaultUnit",
}


def _drop_none(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def platform_document() -> Dict[str, Any]:
    return _drop_none({"@context": PLATFORM_CONTEXT, "@type": "sosa:Platform",
                       **config.PLATFORM})


def sensor_document(sensor_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    return _drop_none({"@context": SENSOR_CONTEXT, "@type": "sosa:Sensor",
                       "sensor_id": sensor_id,
                       "hosted_by": config.PLATFORM["vehicle_id"], **metadata})


def property_document(name: str, unit: str) -> Dict[str, Any]:
    return {"@context": PROPERTY_CONTEXT, "@type": "sosa:ObservableProperty",
            "property_name": name, "unit": unit}


def registration_documents() -> List[Dict[str, Any]]:
    """Todos los metadatos del nodo, en orden: plataforma, propiedades, sensores."""
    docs = [platform_document()]
    docs += [property_document(n, p["unit"]) for n, p in config.OBSERVED_PROPERTIES.items()]
    docs.append(sensor_document(config.PPD42NS_SENSOR_ID, config.PPD42NS_METADATA))
    return docs
