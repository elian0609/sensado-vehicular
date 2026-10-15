# PR · Iteración 3 — Vectores compartidos de identidad (edge_node)

**Rama:** `iter-03-vectores` → `main` · **Repositorio:** edge_node · **No hacer merge hasta la revisión del autor.**
PR hermano: MCS_BACKEND, rama `iter-03-ingesta` (`docs/PR_iter-03.md`).

## Resumen

MCS_BACKEND añade a su contrato v2 unos **vectores de prueba de la regla de identidad** (ADR-002):
`contracts/v2/vectors/identity.json`. Este PR los sincroniza y añade la prueba que los consume, para
garantizar que el `@id` que emite el nodo es exactamente el que el backend recalcula y acepta.
**No cambia el código del nodo**: `semantic/identity.py` ya pasaba todos los casos.

## Cambios

| Archivo | Cambio |
|---|---|
| `tests/fixtures/contracts/vectors/identity.json` | Nuevo, copiado con `sync_fixtures.py` (no se edita a mano) |
| `tests/fixtures/contracts/MANIFEST.sha256` | Incluye el archivo de vectores |
| `tests/test_identity_vectors.py` | Nuevo: un caso por vector + comprobación de `id_base` |
| `CHANGELOG.md`, este archivo | Documentación |

## Vectores

| Caso | Entrada | Resultado esperado |
|---|---|---|
| `ejemplo-real-anexo-a1` | `2026-10-08T16:17:39Z` | `obs/ppd42ns_01/low_pulse_occupancy_ratio/20261008T161739Z` |
| `desfase-menos-0500` | `2026-10-08T11:17:39-05:00` | el mismo `@id` (conversión a UTC) |
| `desfase-cambia-de-dia-y-de-anio` | `2026-12-31T22:30:00-05:00` | `…/20270101T033000Z` |
| `desfase-cero-explicito` | `+00:00` | igual que con `Z` |
| `fracciones-de-segundo-se-descartan` | `…39.999Z` | `…/20261008T161739Z` (trunca) |
| `sensor-id-caracteres-limite`, `sensor-id-un-caracter`, `otra-propiedad` | segmentos límite | `@id` exacto |
| `sin-zona-horaria` | `2026-10-08T16:17:39` | rechazo (`ValueError`, zona horaria) |
| 5 casos de segmento no válido | `-ppd42ns`, `ppd/42`, `ppd 42`, vacío, `lpo#1` | rechazo (`ValueError`) |

## Pruebas

```
$ .venv/bin/pytest
149 passed            (134 anteriores + 15 de vectores)
$ .venv/bin/ruff check . && .venv/bin/ruff format --check .
All checks passed!
```

## Impacto en contratos

Ninguno incompatible: los vectores son un añadido compatible del contrato 2.0.0. KI-1 no cambia.

## Verificación en hardware

No aplica: no cambia nada de lo que se ejecuta en la Pi.
