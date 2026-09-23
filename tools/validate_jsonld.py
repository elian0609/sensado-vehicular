"""
Verificación de los documentos emitidos sobre KI-1.

Para cada documento de la bandeja de salida:
  - lo expande con un procesador JSON-LD 1.1 estándar (pyld);
  - lo convierte a triples RDF (N-Quads);
  - comprueba que estén presentes los términos SOSA que exigen las preguntas
    de competencia PC1-PC6 (la posición, PC6, se satisface recién en KI-2);
  - comprueba que 'raw' no aparezca en la expansión semántica;
  - reporta el tamaño del payload en bytes (métrica de la Fase 6).

Uso:  python3 -m tools.validate_jsonld outbox_ki1.jsonl [--show]
"""
import json
import statistics
import sys

from pyld import jsonld

SOSA = "http://www.w3.org/ns/sosa/"
REQUIRED = {
    "PC1": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
    "PC2": SOSA + "madeBySensor",
    "PC3": SOSA + "observedProperty",
    "PC4": SOSA + "hasSimpleResult",
    "PC5": SOSA + "resultTime",
    "PC6": SOSA + "hasFeatureOfInterest",
}


def check(line: str):
    doc = json.loads(line)
    nquads = jsonld.to_rdf(doc, {"format": "application/n-quads"})
    errors = [f"{pc} ausente" for pc, iri in REQUIRED.items() if f"<{iri}>" not in nquads]
    if "pulse_count" in nquads:
        errors.append("'raw' se filtró a la expansión semántica")
    return len(line.encode()), nquads, errors


def main():
    path, show = sys.argv[1], "--show" in sys.argv
    sizes, failed = [], 0
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(l for l in f if l.strip()):
            size, nquads, errors = check(line.strip())
            sizes.append(size)
            if errors:
                failed += 1
                print(f"[doc {i}] ERROR: {', '.join(errors)}")
            if show and i == 0:
                print("Triples RDF del primer documento:\n" + nquads)
    print(f"Documentos: {len(sizes)} | válidos: {len(sizes) - failed} | "
          f"payload (bytes) min/media/max: {min(sizes)}/"
          f"{statistics.mean(sizes):.1f}/{max(sizes)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
