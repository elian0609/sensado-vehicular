# PR · Iteración 1 — Contrato KI-1 v2, robustez y reproducibilidad

**Rama:** `iter-01-ki1-v2` → `main` · **Repositorio:** edge_node · **No hacer merge hasta la revisión del autor.**

## Resumen

El nodo pasa a emitir el contrato **KI-1 v2.0.0** de `MCS_BACKEND/contracts/v2`: observaciones con
`@id` determinista (ADR-002), `feature_of_interest` como IRI y un nuevo registro
`sosa:FeatureOfInterest` (ADR-008). Además, un fallo en una observación ya no detiene el proceso,
la parada vacía la cola, la configuración operativa se lee del entorno y el repositorio tiene
dependencias fijadas, ruff y 130 pruebas.

## Cambios

| Área | Archivos |
|---|---|
| Contrato v2 | `semantic/identity.py` (nuevo), `semantic/annotator.py`, `semantic/context.py`, `semantic/registry.py`, `sinks/topics.py`, `config.py` (`FEATURES_OF_INTEREST`) |
| Vocabulario | `tools/build_site.py`, `docs/vocab.ttl`, `docs/vocab.html`, `docs/index.html`, `docs/context/ki1.jsonld` |
| Validación | `tools/validate_jsonld.py` (PC1–PC6 de la tesis, modelo v2) |
| Robustez | `core/pipeline.py` (nuevo), `core/observation.py`, `main.py` |
| Configuración | `config.py` (`load_settings`, `EDGE_*`), `deploy/systemd/edge-node.service`, `deploy/edge-node.env.example` |
| M1 | `sensors/ppd42ns.py` (inyección de reloj y `lpo_ratio`) |
| Calidad | `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, formato de todo el repo |
| Pruebas | `tests/conftest.py`, `tests/test_*.py`, `tests/fixtures/contracts/` (copiado de MCS_BACKEND con su manifiesto) |
| Documentación | `README.md`, `CHANGELOG.md`, `docs/ENTORNO_REFERENCIA.md`, `docs/VERIFICACION_HARDWARE.md`, este archivo |

Orden de los commits: configuración → `style:` → **`test:` (pruebas, en rojo)** → `feat!:` contrato
v2 → `refactor:` M1 → `feat:` configuración → `feat:` robustez → `feat(deploy):` → `docs:`.

## Pruebas

```
$ .venv/bin/pytest
130 passed in 1.6 s
$ .venv/bin/ruff check . && .venv/bin/ruff format --check .
All checks passed!
37 files already formatted
```

| Archivo | Casos | Qué comprueba |
|---|---|---|
| `test_contract_ki1.py` | 54 | Telemetría y 4 registros validan contra los esquemas v2 y coinciden con las fixtures; todas las fixtures KI-1 válidas/inválidas; orden de claves; `@context` del código = contrato = `docs/` |
| `test_config.py` | 21 | Valores por defecto, sobrescritura `EDGE_*`, 16 valores inválidos con mensaje que nombra la variable |
| `test_ppd42ns.py` | 12 | LPO exacto con pulsos simulados, límite [0, 1], 6 decimales, `stuck_low`, `result_time` = fin de ventana (en 0,05 s) |
| `test_identity.py` | 10 | Regla ADR-002 exacta, sin zona → error, `-05:00` → UTC, determinismo |
| `test_sinks.py` | 10 | JSON Lines, FanOut con un sink roto, tópicos (incluido el FOI) |
| `test_semantics.py` | 7 | `@id` absoluto, FOI IRI, `raw` sin triples, validador PC1–PC6 |
| `test_pipeline_errors.py` | 7 | Fallo en anotación, serialización, tópico o envío → archivo de errores y el bucle sigue; vaciado al parar con tiempo máximo |
| `test_clock.py` | 7 | Sin cambios de lógica (ahora con pytest) |
| `test_fixtures_manifest.py` | 2 | Las fixtures copiadas coinciden con `MANIFEST.sha256` |

Prueba manual con GPIO simulado (`EDGE_OUTBOX_PATH=... python3 main.py --simulate --sink file --window 1 --max 3`):
7 documentos, `tools.validate_jsonld` → `válidos: 7`; SIGTERM → `Fin: 3 observaciones emitidas, 0 con
error` y salida 0; `EDGE_MQTT_PORT=abc` → `Configuración no válida: EDGE_MQTT_PORT debe ser un int: 'abc'`.

## Impacto en contratos

- **KI-1 pasa a v2.0.0 (incompatible)**: `@id` obligatorio, FOI como IRI, registro FOI nuevo.
- **Compatibilidad con la app actual (sin cambios en MCP_APP):** segura. El registro FOI no entra en
  ningún caso del parser y se ignora sin error (`mqtt_edge_receiver.dart:L232-307`); el `@id` se
  pierde al reconstruir el nodo (`telemetry_observation_entity.dart:L68-82`), pero `result_time` se
  conserva tal cual (`L59-61`), así que el backend deriva el mismo `@id`; lo que la app envía por
  KI-2 no cambia (usa su propio `batchContext` v1). Detalle y cambios pendientes en
  `MCS_BACKEND/docs/arquitectura/BACKLOG.md` (BL-26 a BL-29, Iteración 4).

## Verificación en hardware

**PENDIENTE DE VERIFICACIÓN EN HARDWARE**: `docs/VERIFICACION_HARDWARE.md` (despliegue, dependencias,
4 registros retenidos con `mosquitto_sub`, `@id` en la telemetría, `validate_jsonld` sobre el outbox
nuevo, parada ordenada y app actual). Las versiones de `requirements.txt` no se han confirmado en una
Pi 3B: registrar `pip freeze` en `docs/ENTORNO_REFERENCIA.md`.
