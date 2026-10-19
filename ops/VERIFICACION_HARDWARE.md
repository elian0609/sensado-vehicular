# Verificación en hardware — Iteración 1 (contrato KI-1 v2)

> **VERIFICADO EN HARDWARE el 2026-10-17** (Raspberry Pi 3 Model B Rev 1.2, Debian 13 trixie,
> Python 3.13.5), con `main` en `8fa415e` (contiene `iter-01-ki1-v2` e `iter-03-vectores`).
> Secciones 0–6 completas. Sección 7 ejecutada con la app de la Iteración 4 (MCP_APP `7074e53`)
> en lugar de la app anterior. La Pi y el teléfono estaban en la Wi-Fi de casa ("COCOLON"), no en
> el hotspot: la conexión al hotspot `nodo-moto01` queda para el piloto de campo.
> Las pruebas automáticas (`pytest`) cubren la lógica con GPIO simulado; este procedimiento
> comprueba lo que solo se ve en el dispositivo real.

Cada paso indica el comando exacto y el resultado esperado. Anotar en la columna "Resultado" lo
observado y, si algo falla, detenerse y reportarlo antes de seguir.

Supuestos: el repositorio está clonado en la Pi en `~/sensado-vehicular` (ajustar la ruta si es
otra), el servicio `edge-node` ya estaba instalado (README, "Arranque automático") y Mosquitto corre
en la propia Pi.

## 0. Antes de empezar

| # | Comando (en la Pi) | Resultado esperado | Resultado |
|---|---|---|---|
| 0.1 | `vcgencmd get_throttled` | `throttled=0x0` (alimentación correcta) || `throttled=0x0` |
| 0.2 | `systemctl is-active mosquitto edge-node` | `active` y `active` || `active` `active` |
| 0.3 | `cd ~/sensado-vehicular && git status --short` | Sin cambios locales (si los hay, guardarlos antes) || Sin cambios en archivos versionados. Aparecían como no versionados `outbox_ki1*.jsonl` por un error del `.gitignore` (corregido en la rama `fix/gitignore-outbox`) |
| 0.4 | `cp outbox_ki1.jsonl ~/outbox_ki1_v1_$(date +%Y%m%d).jsonl` | Copia de la bandeja v1 conservada || `~/outbox_ki1_v1_20261017.jsonl` (1 086 743 bytes, 1301 líneas) |

## 1. Desplegar la rama

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 1.1 | `git fetch origin && git checkout iter-01-ki1-v2 && git pull` | `Cambiado a la rama 'iter-01-ki1-v2'`; último commit igual al del PR || Se desplegó `main` (`git pull --ff-only origin main`): `iter-01-ki1-v2` ya estaba fusionada. La Pi iba 16 commits por detrás (`a2f0d25`) |
| 1.2 | `git log --oneline -1` | Coincide con el último commit de `ops/PR_iter-01.md` || `8fa415e Merge pull request #2 from elian0609/iter-03-vectores` |

## 2. Dependencias

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 2.1 | `python3 --version` | Python 3.11.x (Raspberry Pi OS Bookworm). Con una versión anterior el nodo no arranca (`edge_node requiere Python >= 3.11`) || **Python 3.13.5** (Debian 13 trixie, no Bookworm). Cumple `>= 3.11` |
| 2.2 | `uname -m` | `armv7l` o `aarch64` (hay ruedas de `lgpio` para ambos) || `aarch64` |
| 2.3 | `python3 -c "import gpiozero, lgpio, paho.mqtt, pyld; print('ok')"` | `ok` || `ok` |
| 2.4 | `python3 -m pip freeze 2>/dev/null \| grep -iE "gpiozero\|lgpio\|paho\|pyld"` y `dpkg -l python3-gpiozero python3-lgpio python3-paho-mqtt \| tail -3` | Versiones registradas en `ops/ENTORNO_REFERENCIA.md`. Si difieren de `requirements.txt` (gpiozero 2.0.1, lgpio 0.2.2.0, paho-mqtt 2.1.0), anotarlo: **las versiones de `requirements.txt` no se han confirmado en una Pi 3B** || pip: gpiozero 2.0.1, lgpio 0.2.2.0, paho-mqtt 2.1.0, PyLD 3.3.0, rpi-lgpio 0.6. dpkg: python3-gpiozero 2.0.1-0+rpt1+trixie, python3-lgpio 0.2.2-1~rpt1+trixie, python3-paho-mqtt 2.1.0-1. **Coinciden con `requirements.txt`** |
| 2.5 | Completar `ops/ENTORNO_REFERENCIA.md` | Todos los campos rellenos || Completado (`ops/ENTORNO_REFERENCIA.md`) |

## 3. Configuración y servicio

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 3.1 | `sudo cp deploy/systemd/edge-node.service /etc/systemd/system/` | Sin salida || Hecho por el autor. La unidad instalada era anterior: le faltaban `EnvironmentFile` y `TimeoutStopSec` |
| 3.2 | `sudo systemctl edit edge-node` → `[Service]` `User=<usuario>` `WorkingDirectory=<ruta del repo>` (solo si difieren de los del archivo) | Drop-in guardado || No necesario: `User=elian-trelles`, `WorkingDirectory=/home/elian-trelles/sensado-vehicular` coinciden |
| 3.3 | `test -f /etc/edge-node.env \|\| sudo cp deploy/edge-node.env.example /etc/edge-node.env` | Archivo presente (todo comentado = valores por defecto) || `/etc/edge-node.env` creado desde la plantilla (todo comentado) |
| 3.4 | `sudo systemctl daemon-reload && sudo systemctl restart edge-node` | Sin salida || Hecho por el autor (reinicio 20:19:00 -05) |
| 3.5 | `systemctl is-active edge-node` | `active` || `active`; `TimeoutStopUSec=30s`, `EnvironmentFiles=/etc/edge-node.env (ignore_errors=yes)` |
| 3.6 | `journalctl -u edge-node -n 20 --no-pager` | 4 líneas `KI-1 <- registro ... (retain)` (Platform, ObservableProperty, **FeatureOfInterest**, Sensor) y `Sensor ppd42ns_01 activo (ventana 30.0 s)`; ningún `Configuración no válida` || Las 4 líneas `(retain)` (Platform, ObservableProperty, FeatureOfInterest, Sensor) y `Sensor ppd42ns_01 activo (ventana 30.0 s)`; sin `Configuración no válida` |

## 4. Mensajes en el broker

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 4.1 | `mosquitto_sub -h localhost -v -t 'vehiculo/+/+/registro' -t 'vehiculo/plataforma/registro' -W 3` | 4 mensajes retenidos: `vehiculo/plataforma/registro`, `vehiculo/propiedad/low_pulse_occupancy_ratio/registro`, **`vehiculo/foi/ambient_air_at_device/registro`** y `vehiculo/sensor/ppd42ns_01/registro` || Los 4 mensajes retenidos, incluido `vehiculo/foi/ambient_air_at_device/registro` |
| 4.2 | `mosquitto_sub -h localhost -v -t 'vehiculo/sensor/+/observacion' -C 1 -W 70` | Una observación en `vehiculo/sensor/ppd42ns_01/observacion` cuyo JSON empieza por `{"@context":{...},"@id":"obs/ppd42ns_01/low_pulse_occupancy_ratio/20` y contiene `"feature_of_interest":{"@id":"sosa:hasFeatureOfInterest","@type":"@id"}` en el contexto || Empieza por `{"@context":{...`; `@id` `obs/ppd42ns_01/low_pulse_occupancy_ratio/20261018T012401Z`; `feature_of_interest` = `{"@id": "sosa:hasFeatureOfInterest", "@type": "@id"}` |
| 4.3 | Comparar el `@id` de 4.2 con su `result_time` | `@id` = `obs/ppd42ns_01/low_pulse_occupancy_ratio/` + `result_time` sin `-` ni `:` (p. ej. `2026-10-20T14:03:09Z` → `20261020T140309Z`) || `result_time` `2026-10-18T01:24:01Z` → `@id` coincide |
| 4.4 | `mosquitto_sub -h localhost -t 'vehiculo/sensor/+/observacion' -C 1 -W 70 \| wc -c` | ≈ 970–980 bytes (v1: ≈ 885) || 969 bytes (journal: 967–969; v1: 879–881) |

## 5. Validación semántica del outbox nuevo

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 5.1 | Esperar al menos 2 ventanas (≥ 60 s) tras el reinicio del paso 3.4 | — || Más de 5 min tras el reinicio |
| 5.2 | `tail -n 6 outbox_ki1.jsonl > /tmp/outbox_v2.jsonl` | 4 registros + ≥ 2 observaciones v2 (las líneas anteriores al despliegue son v1 y fallarían por no tener `@id`) || Las 6 últimas líneas ya eran observaciones v2 (todas con `@id`). Se validaron además los 6 documentos desde el último `sosa:Platform` (4 registros + 2 observaciones) |
| 5.3 | `python3 -m tools.validate_jsonld /tmp/outbox_v2.jsonl --show` | `Documentos: 6 \| válidos: 6`; aparece `sosa:FeatureOfInterest: 1 doc(s)`; en los triples de la observación el sujeto es `<https://elian0609.github.io/sensado-vehicular/id/obs/...>` (no `_:b0`) y `hasFeatureOfInterest` apunta a `<https://elian0609.github.io/sensado-vehicular/id/ambient_air_at_device>`; código de salida 0 || `Documentos: 6 | válidos: 6` en ambos conjuntos; `sosa:FeatureOfInterest: 1 doc(s)`; sujeto `<https://elian0609.github.io/sensado-vehicular/id/obs/...>` (no `_:b0`); `hasFeatureOfInterest` → `<.../id/ambient_air_at_device>`; código de salida 0 |
| 5.4 | `test -s outbox_ki1_errors.jsonl && cat outbox_ki1_errors.jsonl \|\| echo "sin errores"` | `sin errores` || `sin errores` |

## 6. Parada ordenada

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 6.1 | `sudo systemctl stop edge-node; journalctl -u edge-node -n 5 --no-pager` | `Fin: N observaciones emitidas, 0 con error`; la parada termina en menos de 30 s (`TimeoutStopSec`), sin `SIGKILL` || `Fin: 10 observaciones emitidas, 0 con error`; parada en 0,81 s; sin `SIGKILL` |
| 6.2 | `sudo systemctl start edge-node && systemctl is-active edge-node` | `active` || `active` |

## 7. App con el edge v2

El 2026-10-17 se ejecutó con la app de la Iteración 4 (ya fusionada), no con la anterior.

| # | Acción | Resultado esperado | Resultado |
|---|---|---|---|
| 7.1 | Abrir la app (rama `master` o `feat/aviso-stuck-low`) conectada a la Pi | La tarjeta de telemetría muestra valores nuevos cada 30 s || Con la app de la Iteración 4 (MCP_APP `7074e53`, Infinix X6852, Android 15): KI₁ en verde, LPO nuevo cada 30 s; broker encontrado por `raspberrypi.local` |
| 7.2 | Revisar la consola KI_1 de la app | Aparece `Mensaje MQTT recibido en tópico [vehiculo/foi/ambient_air_at_device/registro]` sin línea de error posterior (la app lo ignora) || El registro FOI se guarda y se envía (la app nueva ya no lo ignora); las observaciones v2 llegan con `@id` como primera clave y el orden de claves del contrato |
| 7.3 | DevTools → Forzar sincronización | Sincroniza como antes (la app aún reenvía el nodo sin `@id`; el backend lo deriva) || Envío automático por T_max (01:29:20Z): lote de 50, 50 insertadas, 0 rechazadas. Las 20 observaciones v2 tienen en el backend `observation_id` = `@base` + `@id` del edge, `device_id = moto_01` y el `gateway_id` de la app |

## 8. Evidencia de alimentación (Iteración 4b, BL-51)

**VERIFICADO EN HARDWARE el 2026-10-19** (17:07–17:15, `main` en `ac5ec6d`, que contiene `iter-04b-campo`). Con el cable bueno, el
2026-10-19 la Pi daba `throttled=0x0` (27 min tras el arranque) y `vcgencmd get_throttled` tardó
3,4 ms; no existe `/sys/devices/platform/soc/soc:firmware/get_throttled` en este kernel (solo
`hwmon1/in0_lcrit_alarm` de `rpi_volt`, sin el valor hexadecimal).

| # | Comando (en la Pi) | Resultado esperado | Resultado |
|---|---|---|---|
| 8.1 | `git fetch origin && git checkout iter-04b-campo && git pull` (o `main` tras la fusión) | Último commit igual al de `ops/PR_iter-04b.md` | `git pull --ff-only origin main` → `ac5ec6d Merge pull request #3 from elian0609/iter-04b-campo` (copia previa del outbox en `~/outbox_ki1_antes_4b_20261019.jsonl`) |
| 8.2 | `sudo systemctl restart edge-node`; esperar 2 ventanas (~1 min) | `active` | El autor reinició el servicio (`sudo` con contraseña): `active` desde las 17:07:51 |
| 8.3 | `vcgencmd get_throttled` | `throttled=0x0` (cable y fuente correctos) | `throttled=0x0` |
| 8.4 | `tail -n2 outbox_ki1.jsonl \| grep -o '"throttled":"[^"]*"'` | `"throttled":"0x0"` en las dos líneas | `"throttled":"0x0"` en las dos líneas (22:08:22Z y 22:08:52Z); mensaje de 987 B (antes 969 B, +18 B) |
| 8.5 | `journalctl -u edge-node --since '-5 min' \| grep -i throttled` | Sin avisos `raw.throttled no disponible` | 0 líneas con `throttled` en el log; `outbox_ki1_errors.jsonl` vacío |
| 8.6 | `tail -n4 outbox_ki1.jsonl > /tmp/outbox_4b.jsonl && python3 -m tools.validate_jsonld /tmp/outbox_4b.jsonl` | `Documentos: 4 \| válidos: 4`; código de salida 0 (`raw` queda fuera de la expansión semántica) | `Documentos: 4 \| válidos: 4`; código de salida 0 |
| 8.7 | En la app: DevTools → consola KI_1 | Las observaciones se guardan como antes (la app no valida `raw`) | App de `master` (`515f2f4`) en modo mesa: las 11 observaciones medidas desde el reinicio (17:08:22–17:13:22) llegaron al backend con `raw.throttled = "0x0"` dentro de `raw_jsonld`; 0 rechazos |

Antes de una captura: lista de comprobación de campo
([`MCS_BACKEND/docs/operacion/CHECKLIST_CAMPO.md`](https://github.com/LeandroFreireGH/MCS_BACKEND/blob/master/docs/operacion/CHECKLIST_CAMPO.md)).

## 9. Campaña del nivel edge (Iteración 5)

**PENDIENTE DE VERIFICACIÓN EN HARDWARE.** Procedimiento de `PROTOCOLO_EXPERIMENTAL.md` §6.2
(MCS_BACKEND, v1.3). Herramientas: `tools/replay.py` (una ejecución) y `tools/experimento_edge.py`
(la campaña). En la PC: `--sin-control-hw`; en la Pi, nunca.

Preparación en la PC (traza sin coordenadas: el nivel edge no las usa y la Pi no las necesita):

```bash
cd MCS_BACKEND
uv run python - <<'EOF'
import json
with open("/tmp/traza_ampliada.jsonl", "w") as o:
    for linea in open("experiment/traces/piloto-ampliada/traza_ampliada.jsonl"):
        n = json.loads(linea)
        for k in ("latitude", "longitude", "position_source"):
            n.pop(k, None)
        o.write(json.dumps(n, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
EOF
cd /tmp && sha256sum traza_ampliada.jsonl > traza_ampliada.sha256
scp traza_ampliada.jsonl traza_ampliada.sha256 <usuario>@<pi>:~/campana/
```

| # | Comando (en la Pi) | Resultado esperado | Resultado |
|---|---|---|---|
| 9.1 | `cd ~/sensado-vehicular && git pull --ff-only origin main && git log --oneline -1` | Commit que contiene `iter-05-edge-experimental` | |
| 9.2 | `cd ~/campana && sha256sum -c traza_ampliada.sha256` | `traza_ampliada.jsonl: La suma coincide` | |
| 9.3 | `sudo systemctl stop edge-node && systemctl is-active edge-node` | `inactive` | |
| 9.4 | `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor` (anotar) y `echo performance \| sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor` | Anterior: `ondemand` (habitual); después, `performance` | |
| 9.5 | Completar `ops/ENTORNO_REFERENCIA.md` (modelo, SO, Python, gobernador) | Entorno anotado con la fecha de la campaña | |
| 9.6 | `vcgencmd measure_temp; vcgencmd get_throttled` (repetir hasta < 50 °C) | `temp` < 50 °C; `throttled=0x0` | |
| 9.7 | `cd ~/sensado-vehicular && python3 -m tools.experimento_edge --trace ~/campana/traza_ampliada.jsonl --out ~/campana/resultados/$(date +%Y%m%d)` | `Campaña completa: 22 ejecuciones`; tabla con mediana y p95 de BORDE y BACKEND; código de salida 0. Si dice `abortada`, anotar el motivo, corregir (fuente, temperatura) y repetir en un directorio nuevo | |
| 9.8 | `head -3 ~/campana/resultados/*/ejecuciones.csv; wc -l ~/campana/resultados/*/*.csv` | 22 ejecuciones (2 de calentamiento, `descartada = true`); `metricas_edge.csv` con 22 × N + 1 líneas | |
| 9.9 | `grep -c ',0x0,0x0,' ~/campana/resultados/*/metricas_edge_ejecucion.csv` | 22 (`get_throttled` = `0x0` al empezar y al terminar cada ejecución) | |
| 9.10 | `echo <gobernador anotado> \| sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor && sudo systemctl start edge-node && systemctl is-active edge-node` | Gobernador restaurado; `active` | |
| 9.11 | En la PC: `scp -r <usuario>@<pi>:~/campana/resultados/<fecha> MCS_BACKEND/experiment/resultados/edge/` | Los cuatro archivos copiados (`ejecuciones.csv`, `metricas_edge.csv`, `metricas_edge_ejecucion.csv`, `campana.meta.json`) | |

**Duración estimada** con la traza de ensayo (5022 observaciones): en la PC, 0,2 s de medición
por ejecución (BORDE 206 ms, BACKEND 147 ms) y 0,4 s con el arranque del proceso, con un pico de RSS
de 24 MiB. En la Pi 3B, entre 10 y 20 veces más lenta en Python, unos 5–8 s por ejecución y
**2–3 min las 22 ejecuciones**, más la espera inicial hasta 50 °C (unos minutos con el servicio
detenido). No hace falta reducir K ni las repeticiones. La medición del 2026-10-19 en la Pi no se
pudo hacer porque la Pi no estaba accesible; esta estimación se confirmará en 9.7.

## Si algo falla: volver a v1

```bash
cd ~/sensado-vehicular && git checkout main && sudo systemctl restart edge-node
```
