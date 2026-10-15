# Verificación en hardware — Iteración 1 (contrato KI-1 v2)

> **PENDIENTE DE VERIFICACIÓN EN HARDWARE.** Ningún paso de este documento se ha ejecutado en la
> Raspberry Pi. Las pruebas automáticas (`pytest`) cubren la lógica con GPIO simulado; este
> procedimiento comprueba lo que solo se ve en el dispositivo real.

Cada paso indica el comando exacto y el resultado esperado. Anotar en la columna "Resultado" lo
observado y, si algo falla, detenerse y reportarlo antes de seguir.

Supuestos: el repositorio está clonado en la Pi en `~/sensado-vehicular` (ajustar la ruta si es
otra), el servicio `edge-node` ya estaba instalado (README, "Arranque automático") y Mosquitto corre
en la propia Pi.

## 0. Antes de empezar

| # | Comando (en la Pi) | Resultado esperado | Resultado |
|---|---|---|---|
| 0.1 | `vcgencmd get_throttled` | `throttled=0x0` (alimentación correcta) | |
| 0.2 | `systemctl is-active mosquitto edge-node` | `active` y `active` | |
| 0.3 | `cd ~/sensado-vehicular && git status --short` | Sin cambios locales (si los hay, guardarlos antes) | |
| 0.4 | `cp outbox_ki1.jsonl ~/outbox_ki1_v1_$(date +%Y%m%d).jsonl` | Copia de la bandeja v1 conservada | |

## 1. Desplegar la rama

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 1.1 | `git fetch origin && git checkout iter-01-ki1-v2 && git pull` | `Cambiado a la rama 'iter-01-ki1-v2'`; último commit igual al del PR | |
| 1.2 | `git log --oneline -1` | Coincide con el último commit de `docs/PR_iter-01.md` | |

## 2. Dependencias

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 2.1 | `python3 --version` | Python ≥ 3.11 (Raspberry Pi OS Bookworm o posterior). Con 3.9/3.10 el nodo no interpreta las horas con `Z` del gateway: reportarlo | |
| 2.2 | `uname -m` | `armv7l` o `aarch64` (hay ruedas de `lgpio` para ambos) | |
| 2.3 | `python3 -c "import gpiozero, lgpio, paho.mqtt, pyld; print('ok')"` | `ok` | |
| 2.4 | `python3 -m pip freeze 2>/dev/null \| grep -iE "gpiozero\|lgpio\|paho\|pyld"` y `dpkg -l python3-gpiozero python3-lgpio python3-paho-mqtt \| tail -3` | Versiones registradas en `docs/ENTORNO_REFERENCIA.md`. Si difieren de `requirements.txt` (gpiozero 2.0.1, lgpio 0.2.2.0, paho-mqtt 2.1.0), anotarlo: **las versiones de `requirements.txt` no se han confirmado en una Pi 3B** | |
| 2.5 | Completar `docs/ENTORNO_REFERENCIA.md` | Todos los campos rellenos | |

## 3. Configuración y servicio

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 3.1 | `sudo cp deploy/systemd/edge-node.service /etc/systemd/system/` | Sin salida | |
| 3.2 | `sudo systemctl edit edge-node` → `[Service]` `User=<usuario>` `WorkingDirectory=<ruta del repo>` (solo si difieren de los del archivo) | Drop-in guardado | |
| 3.3 | `test -f /etc/edge-node.env \|\| sudo cp deploy/edge-node.env.example /etc/edge-node.env` | Archivo presente (todo comentado = valores por defecto) | |
| 3.4 | `sudo systemctl daemon-reload && sudo systemctl restart edge-node` | Sin salida | |
| 3.5 | `systemctl is-active edge-node` | `active` | |
| 3.6 | `journalctl -u edge-node -n 20 --no-pager` | 4 líneas `KI-1 <- registro ... (retain)` (Platform, ObservableProperty, **FeatureOfInterest**, Sensor) y `Sensor ppd42ns_01 activo (ventana 30.0 s)`; ningún `Configuración no válida` | |

## 4. Mensajes en el broker

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 4.1 | `mosquitto_sub -h localhost -v -t 'vehiculo/+/+/registro' -t 'vehiculo/plataforma/registro' -W 3` | 4 mensajes retenidos: `vehiculo/plataforma/registro`, `vehiculo/propiedad/low_pulse_occupancy_ratio/registro`, **`vehiculo/foi/ambient_air_at_device/registro`** y `vehiculo/sensor/ppd42ns_01/registro` | |
| 4.2 | `mosquitto_sub -h localhost -v -t 'vehiculo/sensor/+/observacion' -C 1 -W 70` | Una observación en `vehiculo/sensor/ppd42ns_01/observacion` cuyo JSON empieza por `{"@context":{...},"@id":"obs/ppd42ns_01/low_pulse_occupancy_ratio/20` y contiene `"feature_of_interest":{"@id":"sosa:hasFeatureOfInterest","@type":"@id"}` en el contexto | |
| 4.3 | Comparar el `@id` de 4.2 con su `result_time` | `@id` = `obs/ppd42ns_01/low_pulse_occupancy_ratio/` + `result_time` sin `-` ni `:` (p. ej. `2026-10-20T14:03:09Z` → `20261020T140309Z`) | |
| 4.4 | `mosquitto_sub -h localhost -t 'vehiculo/sensor/+/observacion' -C 1 -W 70 \| wc -c` | ≈ 970–980 bytes (v1: ≈ 885) | |

## 5. Validación semántica del outbox nuevo

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 5.1 | Esperar al menos 2 ventanas (≥ 60 s) tras el reinicio del paso 3.4 | — | |
| 5.2 | `tail -n 6 outbox_ki1.jsonl > /tmp/outbox_v2.jsonl` | 4 registros + ≥ 2 observaciones v2 (las líneas anteriores al despliegue son v1 y fallarían por no tener `@id`) | |
| 5.3 | `python3 -m tools.validate_jsonld /tmp/outbox_v2.jsonl --show` | `Documentos: 6 \| válidos: 6`; aparece `sosa:FeatureOfInterest: 1 doc(s)`; en los triples de la observación el sujeto es `<https://elian0609.github.io/sensado-vehicular/id/obs/...>` (no `_:b0`) y `hasFeatureOfInterest` apunta a `<https://elian0609.github.io/sensado-vehicular/id/ambient_air_at_device>`; código de salida 0 | |
| 5.4 | `test -s outbox_ki1_errors.jsonl && cat outbox_ki1_errors.jsonl \|\| echo "sin errores"` | `sin errores` | |

## 6. Parada ordenada

| # | Comando | Resultado esperado | Resultado |
|---|---|---|---|
| 6.1 | `sudo systemctl stop edge-node; journalctl -u edge-node -n 5 --no-pager` | `Fin: N observaciones emitidas, 0 con error`; la parada termina en menos de 30 s (`TimeoutStopSec`), sin `SIGKILL` | |
| 6.2 | `sudo systemctl start edge-node && systemctl is-active edge-node` | `active` | |

## 7. App actual (sin cambios) con el edge v2

| # | Acción | Resultado esperado | Resultado |
|---|---|---|---|
| 7.1 | Abrir la app (rama `master` o `feat/aviso-stuck-low`) conectada a la Pi | La tarjeta de telemetría muestra valores nuevos cada 30 s | |
| 7.2 | Revisar la consola KI_1 de la app | Aparece `Mensaje MQTT recibido en tópico [vehiculo/foi/ambient_air_at_device/registro]` sin línea de error posterior (la app lo ignora) | |
| 7.3 | DevTools → Forzar sincronización | Sincroniza como antes (la app aún reenvía el nodo sin `@id`; el backend lo deriva) | |

## Si algo falla: volver a v1

```bash
cd ~/sensado-vehicular && git checkout main && sudo systemctl restart edge-node
```
