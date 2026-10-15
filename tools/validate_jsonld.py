"""
Verificación de los documentos emitidos sobre KI-1 (contrato v2).

Para cada documento de la bandeja de salida:
  - lo convierte a triples RDF (N-Quads) con un procesador JSON-LD 1.1 estándar (pyld);
  - comprueba que estén presentes los términos SOSA que exigen las preguntas de
    competencia PC1-PC6 de la tesis (04_metodologia.tex, Fase 3), con el modelo v2:
      PC1 ¿qué tipo de evento?             rdf:type sosa:Observation
      PC2 ¿qué sensor y en qué plataforma?  sosa:madeBySensor (IRI) + isHostedBy en el registro
      PC3 ¿qué propiedad?                   sosa:observedProperty (IRI)
      PC4 ¿qué valor y de qué tipo?         sosa:hasSimpleResult ^^xsd:double
      PC5 ¿en qué instante?                 sosa:resultTime ^^xsd:dateTimeStamp
      PC6 ¿qué objeto del mundo real?       sosa:hasFeatureOfInterest como IRI (ADR-008)
  - comprueba que la observación tenga @id según ADR-002 (IRI bajo config.ID_BASE,
    no un nodo en blanco);
  - comprueba que 'raw' no aparezca en la expansión semántica;
  - reporta el tamaño del payload en bytes (métrica de la Fase 6).

Uso:  python3 -m tools.validate_jsonld outbox_ki1.jsonl [--show]
"""

import json
import statistics
import sys
from datetime import datetime

from pyld import jsonld

import config
from semantic.identity import observation_id

SOSA = "http://www.w3.org/ns/sosa/"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

# PC -> (predicado, forma esperada del objeto: "iri" o el datatype XSD)
REQUIRED = {
    "PC1": (RDF_TYPE, "iri"),
    "PC2": (SOSA + "madeBySensor", "iri"),
    "PC3": (SOSA + "observedProperty", "iri"),
    "PC4": (SOSA + "hasSimpleResult", XSD + "double"),
    "PC5": (SOSA + "resultTime", XSD + "dateTimeStamp"),
    "PC6": (SOSA + "hasFeatureOfInterest", "iri"),
}


def _triples(nquads: str):
    """(sujeto, predicado, objeto) de cada línea N-Quads (sin el punto final)."""
    for linea in nquads.splitlines():
        sujeto, predicado, resto = linea.split(" ", 2)
        yield sujeto, predicado.strip("<>"), resto.rsplit(" ", 1)[0]


def _forma(objeto: str) -> str:
    if objeto.startswith("<"):
        return "iri"
    if "^^<" in objeto:
        return objeto.rsplit("^^<", 1)[1].rstrip(">")
    return "literal"


def _check_observation(doc: dict, triples: list) -> list:
    errors = []
    formas = {p: _forma(o) for _, p, o in triples}
    for pc, (predicado, forma) in REQUIRED.items():
        if predicado not in formas:
            errors.append(f"{pc} ausente")
        elif formas[predicado] != forma:
            errors.append(f"{pc}: se esperaba {forma}, llegó {formas[predicado]}")
    sujetos = {s for s, _, _ in triples}
    if "@id" not in doc or any(s.startswith("_:") for s in sujetos):
        errors.append("sin @id: la observación es un nodo en blanco (ADR-002)")
    else:
        try:
            instante = datetime.fromisoformat(doc["result_time"].replace("Z", "+00:00"))
            esperado = observation_id(doc["sensor_id"], doc["observed_property"], instante)
        except (KeyError, ValueError) as e:
            errors.append(f"@id no verificable: {e}")
        else:
            if doc["@id"] != esperado or sujetos != {f"<{config.ID_BASE}{esperado}>"}:
                errors.append(f"@id no cumple ADR-002 (se esperaba {esperado})")
    return errors


def check(line: str):
    doc = json.loads(line)
    nquads = jsonld.to_rdf(doc, {"format": "application/n-quads"})
    triples = list(_triples(nquads))
    kind = doc.get("@type", "?")
    errors = []
    if not triples:
        errors.append("sin triples")
    if kind == "sosa:Observation":
        errors += _check_observation(doc, triples)
        if "pulse_count" in nquads or "quality_flag" in nquads:
            errors.append("'raw' se filtró a la expansión semántica")
    elif kind == "sosa:Sensor" and not any(p == SOSA + "isHostedBy" for _, p, _ in triples):
        errors.append("PC2 (plataforma) ausente: falta sosa:isHostedBy")
    elif kind == "sosa:FeatureOfInterest" and not any(
        s.startswith(f"<{config.ID_BASE}") for s, _, _ in triples
    ):
        errors.append("PC6: el objeto de interés no es una IRI bajo @base")
    return kind, len(line.encode()), nquads, errors


def main():
    path, show = sys.argv[1], "--show" in sys.argv
    sizes, failed, shown, total = {}, 0, set(), 0
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(ln for ln in f if ln.strip()):
            kind, size, nquads, errors = check(line.strip())
            sizes.setdefault(kind, []).append(size)
            total += 1
            if errors:
                failed += 1
                print(f"[doc {i}, {kind}] ERROR: {', '.join(errors)}")
            if show and kind not in shown:
                shown.add(kind)
                print(f"--- Triples RDF ({kind}, doc {i}):\n" + nquads)
    print(f"Documentos: {total} | válidos: {total - failed}")
    for kind, s in sizes.items():
        print(
            f"  {kind}: {len(s)} doc(s), payload (bytes) min/media/max: "
            f"{min(s)}/{statistics.mean(s):.1f}/{max(s)}"
        )
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
