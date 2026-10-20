# PR · Iteración 7 — BL-60 en el replay del edge

**Rama:** `iter-07-banco` → `main` · **Repositorio:** edge_node · **No hacer merge hasta la revisión del autor.**
PR hermano: MCS_BACKEND `iter-07-banco` (`docs/PR_iter-07.md`: instrumentación del backend,
ejecutor, payload, análisis y ensayo completo del banco).

## Resumen

En la campaña de ensayo de la Pi (2026-10-19), `total_ms / N` incluía unos 89 µs por observación
de registro de la medición. Venían de construir la fila del CSV, calcular el `@id` y tomar `ts_utc`
dentro del bucle (BL-60). Ahora:

- **Dentro del bucle:** solo `perf_counter_ns`, `process_time_ns` y la asignación a listas
  preasignadas (pared, CPU, fin del bloque y referencia al mensaje).
- **Después del bucle:** bytes UTF-8, `@id`, `ts_utc` (derivada de `inicio_utc` y del reloj
  monótono, en orden) y filas.
- **CSV:** se escriben al terminar la ejecución, como antes, fuera de la región medida.

La métrica principal del nivel edge y de H3 sigue siendo la suma de los bloques medidos / N
(protocolo v1.6 §8). `total_ms / N` queda como secundaria y ahora se aproxima a la principal:

| Escenario (PC, 1080 observaciones) | Antes | Ahora |
|---|---|---|
| BORDE: sobrecarga del bucle frente a la suma de bloques | +43 % | +2,0 % |
| BACKEND | +82 % | +3,5 % |

## Commits

| Commit | Tipo | Contenido |
|---|---|---|
| `135be31` | test | `tests/test_replay_medicion.py` **antes de implementar**: 3 de 5 fallaban (orden de las operaciones y sobrecarga) |
| `bc4250d` | feat | Bucle medido con marcas en memoria; registro después |
| (último) | docs | README, CHANGELOG y este PR |

## Evidencia

```
.venv/bin/ruff check .            All checks passed!
.venv/bin/pytest -q               198 passed (193 anteriores + 5 nuevas)
```

El formato de `metricas_edge.csv` y `metricas_edge_ejecucion.csv` no cambia. Las pruebas de la
Iteración 5 siguen en verde: fidelidad byte a byte, contratos, CSV y campaña.

## Pendiente de verificación en hardware

Repetir la campaña de ensayo en la Pi con este código para confirmar que `total_ms / N` se acerca a
la suma de bloques en la Pi (allí la diferencia era de 89 µs). No es necesario para la Iteración 7:
el análisis usa la métrica principal.

## Impacto en la tesis

`04_metodologia.tex`, Fase 6, procedimiento del nivel edge: la región medida contiene solo la
transformación y la serialización, y las marcas se guardan en memoria; la métrica es la suma de los
bloques entre N.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
