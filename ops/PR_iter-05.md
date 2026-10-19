# PR · Iteración 5 — Nivel edge del experimento: replay, modo crudo y campaña (edge_node)

**Rama:** `iter-05-edge-experimental` → `main` · **Repositorio:** edge_node · **No hacer merge hasta la revisión del autor.**
PR hermano: MCS_BACKEND, rama `iter-05-edge-experimental` (`docs/PR_iter-05.md`: traza ampliada y
protocolo v1.3).

## Resumen

Nivel edge del experimento (ADR-004, métrica secundaria, hipótesis H3). El objetivo es medir cuánto
cuesta en la Pi anotar con SOSA/JSON-LD (escenario BORDE) frente a serializar el mensaje crudo
(escenario BACKEND), con la misma traza real.

- **`semantic/annotator.py`: `raw_message()`.** Es el mensaje crudo de KI-1 (ADR-005,
  `ki1-observation-raw` v2, que ya existía): los mismos campos y el mismo orden que `annotate()`,
  sin `@context`, `@id` ni `@type`.
- **`tools/replay.py`** (`python3 -m tools.replay`): una ejecución.
  - **Entradas:** `--trace`, `--scenario {BORDE,BACKEND}`, `--run-id`, `--repeticion` y `--out`.
  - **Entrada de la traza:** lee la traza en JSONL canónico y reconstruye cada `Observation`, el
    contrato de M1 a M2, sin GPIO ni pausas. Ignora la posición que añade la app y recupera el orden
    de `raw` de M1.
  - **Medición por observación** del bloque transformación + serialización: tiempo de pared
    (`perf_counter_ns`), CPU del proceso (`process_time_ns`) y bytes UTF-8.
  - **Medición por ejecución:** CPU y tiempo totales del bucle, RSS al empezar y pico (`VmRSS` y
    `VmHWM` de `/proc/self/status`), temperatura (`/sys/class/thermal`) y `get_throttled` (la sonda
    de BL-51), al empezar y al terminar.
  - **Salida:** añade filas a `metricas_edge.csv` y `metricas_edge_ejecucion.csv`, con las columnas
    del protocolo §7 v1.3.
- **`tools/experimento_edge.py`:** la campaña.
  - **Ejecuciones:** un calentamiento descartado por escenario y 10 ejecuciones por escenario,
    alternadas (BORDE, BACKEND…). Son 22 ejecuciones y cada una corre en un proceso nuevo.
  - **Controles antes de cada ejecución y al terminar:** `get_throttled = 0x0` y temperatura
    ≤ 70 °C (≤ 50 °C antes de la primera). Si un control falla, o no se puede hacer, aborta y
    registra el motivo.
  - **Salida:** `ejecuciones.csv` (§7) y `campana.meta.json`, con el hash de la traza, el commit
    (`git describe --dirty`), el entorno y los parámetros.
  - **Resumen:** imprime la mediana y el p95 por escenario, solo como comprobación.
- **Umbral de 70 °C** (BL-57 en MCS_BACKEND): la Pi 3B empieza a bajar la frecuencia a partir de
  80 °C. Los 10 °C de margen evitan medir con la frecuencia limitada, y cualquier limitación real
  activa además un bit de `get_throttled`.
- **El modo de producción no cambia:** `main.py`, los sinks y M1 no se tocan. El replay no importa
  `sinks`, `paho` ni `gpiozero`; lo comprueba una prueba en un intérprete limpio.

## Commits

| Commit | Tipo | Contenido |
|---|---|---|
| `84bf3f6` | test | `tests/test_replay.py`, `tests/test_experimento_edge.py` y `tests/fixtures/piloto/`, **antes de implementar**: fallaron al recogerse porque `tools.replay`, `tools.experimento_edge` y `raw_message` no existían |
| `2ba8228` | feat | `raw_message`, `tools/replay.py` y `tools/experimento_edge.py` |
| (último) | docs | README, CHANGELOG, `ops/VERIFICACION_HARDWARE.md` §9 y este PR |

## Evidencia

```
.venv/bin/ruff check .            All checks passed!
.venv/bin/ruff format --check .   50 files already formatted
.venv/bin/pytest -q               193 passed (169 anteriores + 24 nuevas)
```

| Criterio de la Iteración 5 (edge) | Evidencia |
|---|---|
| El modo semántico reproduce con fidelidad la traza piloto | `test_modo_semantico_es_semanticamente_identico_a_lo_emitido_en_campo`: URDNA2015 con `pyld`, sin red, idéntico en las 54 observaciones, y `raw` igual. Además, `test_modo_semantico_reproduce_los_bytes_emitidos_en_campo`: **idéntico byte a byte** al outbox de la Pi |
| Crudo valida contra `ki1-observation-raw`; semántico contra `ki1-observation` v2 | `test_cada_mensaje_valida_contra_su_contrato` (54 + 54) |
| CSV con exactamente las columnas del §7 | `test_ejecucion_escribe_los_csv_con_las_columnas_del_protocolo`, `test_campana_de_ensayo_en_procesos_nuevos`. MCS_BACKEND comprueba que el protocolo tiene las mismas columnas |
| No publica en MQTT ni escribe el outbox | `test_el_replay_no_publica_en_mqtt_ni_escribe_el_outbox` |
| Aborto por `get_throttled` o temperatura | `test_aborta_si_la_pi_no_esta_en_condiciones` (4 casos), `test_aborta_a_mitad_si_cambia_el_estado`, `test_temperatura_inicial_por_encima_de_50_no_arranca` |
| Modo de producción sin cambios | Las 169 pruebas anteriores, en verde |

**Campaña de ensayo en la PC** (traza piloto ampliada con K = 5, 270 observaciones, 2 + 2 más un
calentamiento por escenario, `--sin-control-hw`): 6 ejecuciones en 0,7 s, con los cuatro archivos y
las columnas del protocolo. Resumen de comprobación:

```
Escenario  n_obs   mediana_us   p95_us   cpu_mediana_us   bytes_mediana
BORDE        540        29.0     47.4            27.8            969
BACKEND      540        14.6     20.4            13.5            324
```

Ejecución completa con la traza de ensayo (5022 observaciones) en la PC: bucle de 206 ms (BORDE) y
147 ms (BACKEND), 0,4 s por proceso, RSS pico de 24 MiB.

## Pendiente de verificación en hardware

`ops/VERIFICACION_HARDWARE.md` §9 contiene la campaña completa en la Pi:
- servicio detenido;
- gobernador en `performance`;
- entorno registrado;
- hash de la traza comprobado;
- 22 ejecuciones;
- restauración;
- copia de los resultados.

Estimación: unos 5–8 s por ejecución y 2–3 min en total, más la espera hasta 50 °C. No hace falta
ajustar K ni las repeticiones. No pude medir en la Pi porque el 2026-10-19 no estaba accesible
(`No route to host`).

## Riesgos

- **Validez de la extrapolación:** la estimación para la Pi extrapola desde la PC (factor de 10 a 20
  en Python); se confirmará en el paso 9.7.
- **Interferencia entre ejecuciones:** `process_time_ns` mide todo el proceso, pero en el bucle solo
  corre la transformación. El aviso de `raw.throttled` y la escritura de los CSV quedan fuera de la
  medición.
- **Traza en el repositorio público:** `tests/fixtures/piloto/traza_base_sin_posicion.jsonl` publica
  los valores de LPO y las horas del piloto, sin coordenadas (BL-59).

## Impacto en la tesis

`04_metodologia.tex`, **Fase 6** (diseño experimental), apartado del **nivel edge**:
- el replay sobre la traza real ampliada, con el servicio detenido, sin GPIO ni pausas;
- la definición de los dos escenarios en el edge: anotación más serialización frente a
  serialización del mensaje crudo;
- las métricas por observación y por ejecución;
- las condiciones controladas: `get_throttled = 0x0`, temperatura ≤ 70 °C y gobernador en
  `performance`;
- la fidelidad comprobada con la captura piloto.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
