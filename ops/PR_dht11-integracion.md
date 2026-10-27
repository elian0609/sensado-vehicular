# PR · Integración del DHT11 — evaluación de modularidad

**Rama:** `feat/dht11-integration` → `main` · **Base medida:** `eval-dht11-base` (`c332af7`) ·
**Repositorio:** edge_node · **Pruebas E1-E10 superadas (2026-10-27).**
PR hermano: MCS_BACKEND `feat/dht11-integration` (herramientas del experimento, categoría (b)).
MCP_APP: rama creada, **sin cambios**.

## Resumen

Segundo sensor de otro tipo de dato, el Seeed Studio Grove DHT11 (temperatura y humedad relativa,
bus digital de un hilo), integrado para medir el **costo de integración** de la arquitectura
(`_evaluacion_modularidad/plan.md`, fuera del repositorio). El costo se separa en (a) arquitectura
(nodo, app y backend en ejecución) y (b) herramientas del experimento.

- **Lectura:** driver `dht11` del kernel (`dtoverlay=dht11,gpiopin=23`), que valida el checksum y
  expone la medición en IIO. `sensors/dht11.py` lee `in_temp_input` e
  `in_humidityrelative_input` cada 30 s y devuelve dos `Observation` de la misma medición:
  `air_temperature` (`degree_celsius`) y `relative_humidity` (`percent_rh`), con el mismo
  `result_time`, `feature_of_interest = ambient_air_at_device` y `raw` en su orden natural
  (`gpio_pin_bcm`, `window_seconds` = duración real de la lectura, `quality_flag = ok`). Una
  lectura rechazada por el driver se propaga como `OSError`: `acquisition_loop` la registra y no
  hay observación. Sin dependencias nuevas.
- **Registro:** solo `config.py` (bloque, `SENSOR_METADATA`, `OBSERVED_PROPERTIES`) y una sentencia
  en `build_sensors()`. `semantic/registry.py`, el `@context`, los contratos v2 y los tópicos no
  cambian.
- **Cola de Mosquitto:** 25 h × 3600 × (1/30 + 2/30) = 9000.
- **Herramientas (b):** `tools/replay.py` deja de reordenar `raw` con el orden del PPD42NS
  (`ORDEN_RAW`); el mensaje reproducido tiene la misma longitud en bytes y el mismo documento que el
  emitido, aunque el orden de `raw` puede diferir (decisión del autor).

## Commits

| Commit | Categoría | Contenido | `--numstat` |
|---|---|---|---|
| `c96db2a` | (a) M1 | `sensors/dht11.py` y `tests/test_dht11.py` (8 casos) | +90; +129 |
| `a5198de` | (a) M1 y configuración | `config.py`, sentencia en `build_sensors()`, 2 casos | `config.py` +17/−0; `main.py` +8/−0; pruebas +49 |
| `5dd663f` | (a) configuración | `deploy/mosquitto/ki1.conf`: 9000 | +2/−2 |
| `fcb81ec` | (a) comentarios | Comentarios desfasados en `build_sensors()` y `autosave_interval` | +2/−2 |
| `1fa3cb1` | (b) herramientas | `tools/replay.py` sin `ORDEN_RAW`; 2 pruebas existentes ajustadas y 1 nueva | `replay.py` +4/−10; `test_replay.py` +43/−6 |
| (este) | documentación | README, `ops/VERIFICACION_HARDWARE.md` §10, este PR y CHANGELOG | — |

Total contra la base (código y pruebas): `config.py` +17/−0, `main.py` +9/−1, `ki1.conf` +3/−3,
`sensors/dht11.py` +90, `tests/test_dht11.py` +178, `tools/replay.py` +4/−10,
`tests/test_replay.py` +43/−6. MCS_BACKEND: `tools/criterios_traza.py` +28/−6, `tools/payload.py`
+6/−13 y sus pruebas.

## Evidencia

- Pruebas en rojo antes de cada cambio. edge_node: 209 pasan (198 de la base + 10 del DHT11 + 1 de
  replay), `ruff` limpio. MCS_BACKEND: 1348 con `EDGE_NODE_REQUIRED=1` (compatibilidad contra este
  edge). MCP_APP: 110, `flutter analyze` y `dart format` limpios.
- **Costo (a):** 0 archivos en MCP_APP y MCS_BACKEND; 0 líneas en `sensors/base.py`, `core/`,
  `semantic/`, `sinks/` y contratos; 0 pruebas existentes modificadas; 0 dependencias. `main.py`: una
  sentencia de 7 líneas físicas + `import` (umbral ≤ 8). **Localidad C4 = 0,78** (umbral 0,80): el
  registro cuesta ~25 líneas en `config.py` y `main.py` (comentarios del bloque y formateo de una
  sentencia), no un acoplamiento.
- **Costo (b):** los 3 archivos previstos (`replay.py`, `payload.py`, `criterios_traza.py`), sin
  referencias al DHT11; 4 pruebas existentes modificadas porque fijaban el orden de `raw` del
  PPD42NS o la igualdad byte a byte.
- En la Pi (2026-10-27): línea base del PPD42NS, cableado y V1-V5 del driver
  (`ops/VERIFICACION_HARDWARE.md` §10.1).

## Verificación en hardware (2026-10-27, `ops/VERIFICACION_HARDWARE.md` §10.2)

Sesión "después" en las mismas condiciones que la línea base estabilizada (reinicio del servicio,
5 min de estabilización, ventana de 26 min). **E1-E10 superadas:**

| Prueba | Resultado |
|---|---|
| E1 | 7 registros retenidos; los dos sensores activos (ventana 30.0 s) |
| E2 / E3 | 52 PPD42NS y 52 lecturas del DHT11 (104 observaciones); lecturas válidas 52/52 |
| E4 | `@id` de la ventana: outbox 156 = backend 156 |
| E5 | 156/156 y 7/7 válidos; PC2 y PC3 con `dht11_01` |
| E6 | 22-23 °C, 36-38 %RH |
| E7 | SIG desconectado 5 min: PPD42NS sin huecos; DHT11 con 11 fallos solo en el log; recuperación sin reiniciar |
| E8 | Tarjeta con `observed_property` y `unit`; sin anomalías de ventana |
| E9 | El mapa solo muestra LPO (52 puntos) |
| E10 | ≈ 19,8 MB de RSS de Mosquitto con 9000 mensajes (614 MB disponibles); ráfaga de 127 entregada |

**No regresión del PPD42NS:** 52 observaciones, 30,0 s, `ok`/`0x0`, 982-987 bytes (antes 981-987),
CPU 4,66 % (antes 4,73 %), RSS +0,1-0,2 MB.

**Hallazgos de la ejecución:** el panel RAW de la app tenía campos fijos del PPD42NS (acoplamiento
residual de presentación, corregido en MCP_APP); el DHT11 se ubica casi siempre como
`trayectoria_cercana` (medición puntual, ventana ≈ 0,04 s), consecuencia válida del diseño de M3.

## Impacto en la tesis

- Fase 6, evaluación del desacoplamiento modular: costo de integración (a) y (b) con sus umbrales;
  C4 = 0,78 reportado sin modificar el umbral.
- `04_metodologia.tex:222`: el DHT11 entra sin modificar el modelo de datos, M2 ni el orquestador más
  allá de una sentencia de registro y su bloque en `config.py`; nombres `air_temperature` y
  `relative_humidity`.
- Protocolo §7: la garantía del replay y del payload pasa de "idéntico byte a byte" a "misma
  longitud en bytes y mismo documento JSON".
- Periodo de estabilización de 5 min (transitorio de arranque del servicio, causa no determinada).
