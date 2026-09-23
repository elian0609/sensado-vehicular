"""
Genera el sitio estático que publica el vocabulario del proyecto (proy:) y el
@context de KI-1, a partir de config.py y semantic/context.py (fuente única).

Uso:  python3 -m tools.build_site docs
Luego publicar la carpeta docs/ con GitHub Pages.
"""
import html
import json
import os
import sys

import config
from semantic.context import KI1_TELEMETRY_CONTEXT

SOSA = "http://www.w3.org/ns/sosa/"

# (término, dominio, rango, etiqueta, comentario) — los 10 términos del DIV-3
TERMS = [
    ("unit", "sosa:Observation", "xsd:string", "unidad",
     "Unidad de medida asociada al valor de una observación."),
    ("defaultUnit", "sosa:ObservableProperty", "xsd:string", "unidad por defecto",
     "Unidad de medida por defecto de una propiedad observada."),
    ("sensorModel", "sosa:Sensor", "xsd:string", "modelo del sensor",
     "Modelo físico del dispositivo sensor (p. ej. PPD42NS)."),
    ("sensorType", "sosa:Sensor", "xsd:string", "tipo de sensor",
     "Categoría de magnitud que mide el dispositivo (catálogo abierto)."),
    ("calibrationParams", "sosa:Sensor", "rdf:JSON", "parámetros de calibración",
     "Parámetros de calibración propios del sensor, como objeto JSON."),
    ("installDate", "sosa:Sensor", "xsd:date", "fecha de instalación",
     "Fecha de instalación física del sensor sobre la plataforma vehicular."),
    ("status", "sosa:Sensor", "xsd:string", "estado",
     "Estado operativo del dispositivo (activo / inactivo)."),
    ("vehicleType", "sosa:Platform", "xsd:string", "tipo de vehículo",
     "Tipo de vehículo sobre el que opera la plataforma."),
    ("routeLabel", "sosa:Platform", "xsd:string", "etiqueta de ruta",
     "Identificador de la ruta urbana recorrida por la plataforma."),
    ("registrationDate", "sosa:Platform", "xsd:date", "fecha de registro",
     "Fecha de alta de la plataforma dentro del sistema."),
]


def turtle() -> str:
    lines = [
        f"@prefix proy: <{config.VOCAB_NS}> .",
        f"@prefix sosa: <{SOSA}> .",
        "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix owl:  <http://www.w3.org/2002/07/owl#> .",
        "@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix dct:  <http://purl.org/dc/terms/> .",
        "",
        f"<{config.VOCAB_NS.rstrip('#')}> a owl:Ontology ;",
        '    dct:title "Vocabulario de extensión para sensado vehicular oportunista"@es ;',
        f"    owl:imports <{SOSA}> .",
        "",
    ]
    for term, dom, rng, label, comment in TERMS:
        lines += [
            f"proy:{term} a owl:DatatypeProperty ;",
            f'    rdfs:label "{label}"@es ;',
            f'    rdfs:comment "{comment}"@es ;',
            f"    rdfs:domain {dom} ;",
            f"    rdfs:range {rng} ;",
            f"    rdfs:isDefinedBy <{config.VOCAB_NS.rstrip('#')}> .",
            "",
        ]
    return "\n".join(lines)


def vocab_html() -> str:
    rows = "\n".join(
        f'<tr id="{t}"><td><code>proy:{t}</code></td><td>{html.escape(l)}</td>'
        f"<td><code>{d}</code></td><td><code>{r}</code></td><td>{html.escape(c)}</td></tr>"
        for t, d, r, l, c in TERMS)
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vocabulario proy:</title>
<link rel="alternate" type="text/turtle" href="vocab.ttl">
<style>body{{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:.4rem;text-align:left;vertical-align:top}}
:target{{background:#fff6c7}}</style></head><body>
<h1>Vocabulario de extensión <code>proy:</code></h1>
<p>Espacio de nombres: <code>{config.VOCAB_NS}</code>. Extiende SOSA/SSN
(<code>{SOSA}</code>) solo con los términos que SOSA no define.
Versión legible por máquina: <a href="vocab.ttl">vocab.ttl</a>.
Contexto JSON-LD de KI-1: <a href="context/ki1.jsonld">context/ki1.jsonld</a>.</p>
<table><tr><th>Término</th><th>Etiqueta</th><th>Dominio</th><th>Rango</th><th>Definición</th></tr>
{rows}</table></body></html>"""


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "docs"
    if "tuproyecto.org" in config.PROJECT_NS:
        sys.exit("Primero reemplaza PROJECT_NS en config.py por tu dominio real.")
    os.makedirs(os.path.join(out, "context"), exist_ok=True)
    files = {
        "vocab.ttl": turtle(),
        "vocab.html": vocab_html(),
        "index.html": vocab_html(),
        "context/ki1.jsonld": json.dumps({"@context": KI1_TELEMETRY_CONTEXT},
                                         indent=2, ensure_ascii=False),
        ".nojekyll": "",
    }
    for name, content in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(content)
        print("generado", os.path.join(out, name))


if __name__ == "__main__":
    main()
