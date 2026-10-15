# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). La versión sigue la
del contrato KI-1 que emite el nodo (`MCS_BACKEND/contracts/`).

## [2.0.1] — Iteración 3 (rama `iter-03-vectores`)

### Añadido
- `tests/test_identity_vectors.py`: la regla de ADR-002 (`semantic/identity.py`) se prueba con los
  vectores compartidos de `MCS_BACKEND/contracts/v2/vectors/identity.json`, los mismos que usa el
  backend. Sin cambios en el código del nodo.

## [2.0.0] — Iteración 1 (rama `iter-01-ki1-v2`) — CAMBIO INCOMPATIBLE

### Cambiado (incompatible)
- Contrato **KI-1 v2.0.0**: cada observación lleva `@id`
  `obs/{sensor_id}/{observed_property}/{YYYYMMDDTHHMMSSZ}` (ADR-002), justo después de `@context`.
- `feature_of_interest` se expande como **IRI** (`"@type": "@id"`), no como literal (ADR-008).
- El mensaje de telemetría crece de ≈ 885 B a ≈ 973 B (`@id` y tipado del FOI en el `@context`).

### Añadido
- `semantic/identity.py`: única implementación de la regla del `@id`.
- Registro `sosa:FeatureOfInterest` (`ambient_air_at_device`) retenido en
  `vehiculo/foi/{feature_id}/registro`, publicado al arrancar con los otros tres.
- Término `proy:featureKind` en el vocabulario; `docs/` regenerado.
- `core/pipeline.py`: un fallo en una observación se registra en `outbox_ki1_errors.jsonl` y el
  bucle continúa; parada ordenada (SIGTERM/SIGINT) con vaciado de la cola.
- Configuración operativa por variables `EDGE_*` con validación al arrancar;
  `EnvironmentFile=-/etc/edge-node.env` en el servicio y `deploy/edge-node.env.example`.
- `requirements.txt` y `requirements-dev.txt` con versiones fijadas; `pyproject.toml` con ruff y pytest.
- Pruebas pytest (130): contrato v2 con las fixtures sincronizadas de MCS_BACKEND, identidad,
  semántica RDF, M1 con GPIO simulado, sinks, robustez y configuración.
- `ops/ENTORNO_REFERENCIA.md` y `ops/VERIFICACION_HARDWARE.md`.
- `ops/`: documentación operativa (verificación en hardware, entorno de referencia, PR), fuera
  de `docs/`, que es el sitio publicado en GitHub Pages; `tests/test_docs_site.py` impide publicar
  en `docs/` algo que no esté en la lista permitida (BL-33).
- Requisito **Python ≥ 3.11** (Raspberry Pi OS Bookworm): `requires-python` en `pyproject.toml`,
  comprobación al arrancar en `config.py` y ruff con `target-version = "py311"` (BL-32).

### Cambiado
- `tools/validate_jsonld.py` comprueba PC1–PC6 de la tesis con el modelo v2 (`@id` presente, FOI IRI).
- `sensors/ppd42ns.py`: reloj, pausa y hora inyectables (solo pruebas) y función `lpo_ratio`.
- Todo el repositorio pasa `ruff check` y `ruff format` (sin cambios de comportamiento).

## [1.x] — hasta el commit `a2f0d25`
- Contrato KI-1 v1 (observaciones como nodos en blanco, FOI literal). Ver historial de git.
