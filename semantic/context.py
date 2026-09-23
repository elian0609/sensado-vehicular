"""
@context JSON-LD 1.1 de la telemetría emitida sobre KI-1 (DIV-3).

Corrige respecto al borrador del DIV-3:
  - declara los prefijos xsd y proy, usados pero no declarados;
  - declara @base, sin el cual los identificadores compactos quedan como IRIs
    relativas que se descartan al convertir a RDF;
  - tipa result_time como xsd:dateTimeStamp (rango exigido por sosa:resultTime).
"""
import config

SOSA = "http://www.w3.org/ns/sosa/"
XSD = "http://www.w3.org/2001/XMLSchema#"

KI1_TELEMETRY_CONTEXT = {
    "@base": config.ID_BASE,
    "sosa": SOSA,
    "xsd": XSD,
    "proy": config.VOCAB_NS,
    "sensor_id": {"@id": "sosa:madeBySensor", "@type": "@id"},
    "observed_property": {"@id": "sosa:observedProperty", "@type": "@id"},
    "value": {"@id": "sosa:hasSimpleResult", "@type": "xsd:double"},
    "result_time": {"@id": "sosa:resultTime", "@type": "xsd:dateTimeStamp"},
    "feature_of_interest": "sosa:hasFeatureOfInterest",
    "unit": "proy:unit",
    # 'raw' se omite deliberadamente: fuera de la expansión semántica.
}
