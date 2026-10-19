# PR · Iteración 4b — Evidencia de alimentación en `raw.throttled` (edge_node)

**Rama:** `iter-04b-campo` → `main` · **Repositorio:** edge_node · **No hacer merge hasta la revisión del autor.**
PR hermanos: MCS_BACKEND y MCP_APP, rama `iter-04b-campo` (`docs/PR_iter-04b.md` en cada uno).

## Resumen

Durante la captura piloto del 2026-10-19 hubo bajo voltaje en la Pi (11:36:33–11:38:26), y las
lecturas afectadas no se distinguen en los datos. El autor decidió **resolverlo en hardware**: con un
cable adecuado, `vcgencmd get_throttled` da `0x0`. Por eso no se añade ningún valor a `quality_flag`.
El nodo solo guarda, como evidencia, el valor de `get_throttled` al cerrar cada ventana (BL-51).

- `sensors/throttled.py`: `leer_vcgencmd()` lanza `vcgencmd get_throttled` con un límite de 1 s y
  normaliza la salida a `"0x…"`. `ThrottledProbe` nunca falla: si el lector no está disponible
  devuelve `None`, avisa **una sola vez** en el log y lo vuelve a intentar en la ventana siguiente.
- `sensors/ppd42ns.py`: lector inyectable (`throttled=`), con vcgencmd por defecto. Se lee
  **después** de medir la ventana y fijar `result_time`, y **fuera** del cerrojo de los pulsos: la
  duración de la ventana, el LPO y `result_time` no cambian, y los flancos del GPIO siguen
  registrándose mientras se lee. El valor va en `raw.throttled`.
- **Contrato:** sin cambios. En KI-1 v2, `raw` admite campos libres; la salida sigue validando
  contra `ki1-observation` v2 (probado con `"0x0"` y con `null`).
- **No existe una interfaz equivalente en `/sys`:** en la Pi de referencia no hay
  `/sys/devices/platform/soc/soc:firmware/get_throttled`. Solo existe `in0_lcrit_alarm` de
  `rpi_volt`, que da el bajo voltaje actual (0/1) y no el valor hexadecimal. `vcgencmd` tardó
  3,4 ms en la Pi 3B.

**Incluye además dos commits que solo existían en local** (no se habían subido; ya revisados en la
sesión del 2026-10-17):
- `d7bdbb3` (de `fix/gitignore-outbox`): `.gitignore` con `outbox_ki1*.jsonl` y `.venv/` en
  líneas separadas.
- `3378d5d` (de `ops/verificacion-hw-20261017`): resultados de la verificación en hardware del
  2026-10-17 y `ops/ENTORNO_REFERENCIA.md`.

Las ramas locales `fix/gitignore-outbox` y `ops/verificacion-hw-20261017` quedan sustituidas por
esta.

## Commits

| Commit | Tipo | Contenido |
|---|---|---|
| `d7bdbb3` | fix | `.gitignore` (cherry-pick de `91731b3`) |
| `3378d5d` | ops | Verificación en hardware del 2026-10-17 (cherry-pick de `33cf562`) |
| `52e2c54` | test | `tests/test_throttled.py`, **antes de implementar**: falló al recogerse porque `sensors.throttled` no existía; `_sensor` de `test_ppd42ns.py` con un lector falso |
| `d13894e` | feat | `sensors/throttled.py` y `raw.throttled` en `sensors/ppd42ns.py` |
| (último) | docs | README, CHANGELOG, `ops/VERIFICACION_HARDWARE.md` §8 y este PR |

## Evidencia

```
.venv/bin/ruff check .            All checks passed!
.venv/bin/ruff format --check .   45 files already formatted
.venv/bin/pytest -q               169 passed (20 nuevas en tests/test_throttled.py)
```

| Criterio de la Iteración 4b | Prueba |
|---|---|
| `raw.throttled` en hexadecimal al cerrar cada ventana | `test_cada_ventana_guarda_el_valor_en_raw`, `test_vcgencmd_se_normaliza_a_hexadecimal` |
| Sin lector: el nodo sigue, avisa una vez y guarda `null` | `test_sin_lector_disponible_el_nodo_sigue_y_guarda_null`, `test_sonda_sin_lector_disponible_devuelve_none_y_avisa_una_vez` |
| No bloquea los pulsos ni altera la ventana | `test_la_lectura_no_altera_la_ventana`, `test_la_lectura_se_hace_fuera_del_cerrojo_de_los_pulsos` |
| Valida contra `ki1-observation` v2 sin cambios | `test_la_salida_sigue_validando_contra_ki1_observation_v2` (`"0x0"` y `null`) |

## Pendiente de verificación en hardware

`ops/VERIFICACION_HARDWARE.md` §8: desplegar la rama en la Pi y comprobar que `raw.throttled` aparece
en el outbox y vale `"0x0"` con el cable bueno, sin avisos en el log.

## Riesgos

- El mensaje KI-1 crece unos 19 B (`,"throttled":"0x0"`). Las fixtures del contrato no lo incluyen:
  el payload de referencia del protocolo (973 B) no cambia, pero las trazas reales sí.
- `vcgencmd` necesita acceso a `/dev/vcio` (grupo `video`). Si el servicio corriera con otro usuario
  sin ese grupo, `raw.throttled` sería `null` (con un aviso) y el nodo seguiría funcionando.

## Impacto en la tesis

- `04_metodologia.tex`, Fase 1 (nodo edge, M1) y Fase 6 (protocolo de campo): el nodo registra en
  `raw.throttled` la evidencia de alimentación de cada ventana, y la verificación `get_throttled = 0x0`
  es un paso del protocolo de campo (lista de comprobación de MCS_BACKEND).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
