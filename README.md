# Nodo Edge (H2) — M1 + M2 y publicación en KI-1

```
PPD42NS --GPIO4--> M1 (sensors/ppd42ns.py, hilo propio, ventana 30 s)
DHT11 --GPIO23 (driver dht11 del kernel, IIO)--> M1 (sensors/dht11.py, hilo propio, cada 30 s)
                     |  Observation (contrato interno, sin semántica)
                     v
                   M2 (semantic/annotator.py) --> JSON-LD 1.1
                     |
                     v
                   KI-1: MqttSink (sinks/mqtt.py) --> broker Mosquitto (en la Pi)
                                                         |
                                                         v
                                              Gateway local (app móvil, H3)
```

## Contrato KI-1 v2

El nodo emite el **contrato KI-1 v2.0.0**, definido y versionado en
[`MCS_BACKEND/contracts/v2`](https://github.com/LeandroFreireGH/MCS_BACKEND/tree/master/contracts)
(esquemas JSON Schema, `@context` y fixtures). Cambios frente a v1 (incompatibles, ver `CHANGELOG.md`):

- Cada observación lleva **`@id`** según ADR-002:
  `obs/{sensor_id}/{observed_property}/{result_time UTC en formato YYYYMMDDTHHMMSSZ}`, relativo a
  `@base`. La regla vive solo en `semantic/identity.py`; el backend aplica la misma.
- `feature_of_interest` es una **IRI** (`{"@id": "sosa:hasFeatureOfInterest", "@type": "@id"}`,
  ADR-008), y se publica un **registro `sosa:FeatureOfInterest`** para ella.
- `raw.quality_flag` y `raw.clock_source` son obligatorios.

Las fixtures del contrato se copian a `tests/fixtures/contracts/` con
`MCS_BACKEND/contracts/tools/sync_fixtures.py sync --dest ../edge_node/tests/fixtures/contracts --yes`;
`tests/test_fixtures_manifest.py` falla si alguien las edita a mano.

### Tópicos

| Mensaje | Tópico | Sentido | QoS | Retain |
|---|---|---|---|---|
| Telemetría | `vehiculo/sensor/{sensor_id}/observacion` | nodo → gateway | 1 | no |
| Registro de plataforma | `vehiculo/plataforma/registro` | nodo → gateway | 1 | sí |
| Registro de propiedad | `vehiculo/propiedad/{property_name}/registro` | nodo → gateway | 1 | sí |
| Registro de objeto de interés (**nuevo en v2**) | `vehiculo/foi/{feature_id}/registro` | nodo → gateway | 1 | sí |
| Registro de sensor | `vehiculo/sensor/{sensor_id}/registro` | nodo → gateway | 1 | sí |
| Hora del teléfono | `vehiculo/gateway/hora` | gateway → nodo | 0 | no |

- Broker: puerto 1883, MQTT v3.1.1, sin autenticación (WLAN privada del hotspot).
- El gateway debe suscribirse a `vehiculo/#` con QoS 1, un `client_id` fijo y
  `clean_session = false`, para que el broker le guarde lo publicado mientras
  esté desconectado.
- Los registros pueden llegar repetidos (se reenvían al volver a suscribirse):
  el gateway debe tratarlos como actualización por identificador, no como alta.
- Hora del teléfono: `{"utc": "2026-10-06T23:10:05.123Z", "fuente": "telefono"}`,
  publicada por el gateway al conectarse y cada 10 min. Si el nodo no tiene NTP,
  corrige su reloj y el RTC cuando el desfase supera 1 s (nunca retrocede más de
  20 s, para no repetir `result_time`). Ver `core/clock.py`.
- Cada observación indica en `raw.clock_source` de dónde venía la hora del nodo:
  `ntp`, `gateway` (corregida o confirmada en las últimas 6 h) o `rtc`.

### Ejemplos reales (salida de `annotate()` y `registration_documents()`)

Telemetría (en el canal viaja compacta en una línea: **973 B**; v1 ocupaba 885 B):

```json
{
  "@context": {
    "@base": "https://elian0609.github.io/sensado-vehicular/id/",
    "sosa": "http://www.w3.org/ns/sosa/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "proy": "https://elian0609.github.io/sensado-vehicular/vocab#",
    "sensor_id": {"@id": "sosa:madeBySensor", "@type": "@id"},
    "observed_property": {"@id": "sosa:observedProperty", "@type": "@id"},
    "value": {"@id": "sosa:hasSimpleResult", "@type": "xsd:double"},
    "result_time": {"@id": "sosa:resultTime", "@type": "xsd:dateTimeStamp"},
    "feature_of_interest": {"@id": "sosa:hasFeatureOfInterest", "@type": "@id"},
    "unit": "proy:unit"
  },
  "@id": "obs/ppd42ns_01/low_pulse_occupancy_ratio/20261008T161739Z",
  "@type": "sosa:Observation",
  "sensor_id": "ppd42ns_01",
  "observed_property": "low_pulse_occupancy_ratio",
  "value": 0.133345,
  "unit": "ratio_0_1",
  "result_time": "2026-10-08T16:17:39Z",
  "feature_of_interest": "ambient_air_at_device",
  "raw": {"pulse_count": 38, "low_time_seconds": 4.0004, "window_seconds": 30.0,
          "gpio_pin_bcm": 4, "quality_flag": "ok", "clock_source": "gateway"}
}
```

Registros (cada uno lleva además su `@context`: `SENSOR_CONTEXT`, `PLATFORM_CONTEXT`,
`PROPERTY_CONTEXT` y `FOI_CONTEXT` en `semantic/registry.py`):

```json
{"@type": "sosa:Platform", "vehicle_id": "moto_01", "vehicle_type": "motocicleta", "registration_date": "2026-09-24"}
{"@type": "sosa:ObservableProperty", "property_name": "low_pulse_occupancy_ratio", "unit": "ratio_0_1"}
{"@type": "sosa:FeatureOfInterest", "feature_id": "ambient_air_at_device", "feature_kind": "aire_ambiente", "description": "Aire ambiente en el punto de toma del sensor, a bordo de la plataforma"}
{"@type": "sosa:Sensor", "sensor_id": "ppd42ns_01", "hosted_by": "moto_01", "sensor_model": "PPD42NS", "sensor_type": "particulate_matter", "calibration_params": {"voltage_divider_r1_ohm": 1000, "voltage_divider_r2_ohm": 2000}, "install_date": "2026-10-05", "status": "activo"}
```

El `@context` publicado (`docs/context/ki1.jsonld`) y el vocabulario `proy:` (`docs/vocab.ttl`,
con `proy:featureKind`) se regeneran con `python3 -m tools.build_site docs`.

## Instalación en la Raspberry Pi

**Requisito: Python ≥ 3.11** (la Pi de referencia, una Raspberry Pi 3B, corre Raspberry Pi OS sobre
Debian 13 **trixie**, con Python 3.13). El nodo se niega a
arrancar con una versión anterior (`config.py`), y `core/clock.py` necesita 3.11 para interpretar las
horas con sufijo `Z` que publica el gateway. Comprobación: `python3 --version`.
```bash
cd ~ && git clone https://github.com/elian0609/sensado-vehicular.git
cd sensado-vehicular
sudo apt install -y python3-gpiozero python3-lgpio python3-paho-mqtt \
                    mosquitto mosquitto-clients avahi-daemon
pip3 install pyld --break-system-packages      # solo para validar
# Versiones de referencia: requirements.txt (registrar las reales con `pip freeze`
# en ops/ENTORNO_REFERENCIA.md). Alternativa en entorno virtual:
#   python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements.txt

# Broker de KI-1 (escucha en la WLAN, persistencia cada 10 s)
sudo cp deploy/mosquitto/ki1.conf /etc/mosquitto/conf.d/ki1.conf
sudo systemctl enable --now mosquitto && sudo systemctl restart mosquitto

# Anuncio del broker por DNS-SD (_mqtt._tcp) para que el gateway lo descubra
sudo cp deploy/avahi/ki1-mqtt.service /etc/avahi/services/ki1-mqtt.service
sudo systemctl reload avahi-daemon

# Registros del sistema persistentes: sin esto, journalctl se borra en cada
# reinicio y no se puede diagnosticar lo ocurrido antes de un corte de energía
sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald
```

### Hardware
- **Alimentación:** 5,1 V / 2,5 A (fuente oficial o equivalente); en el vehículo,
  convertidor 12 V → 5 V de al menos 3 A. Un puerto USB de laptop no basta: provoca
  bajo voltaje, caídas del Wi-Fi y lecturas en cero. Comprobación:
  `vcgencmd get_throttled` debe devolver `throttled=0x0`.
- **Señal del PPD42NS:** P1 (5 V) → 1 kΩ → GPIO4 (pin 7), con 2 kΩ de GPIO4 a GND,
  y el GND del sensor unido al de la Pi. Sin la resistencia a GND el pin recibe más
  de 3,3 V y la señal rebota (miles de pulsos de < 1 ms que no son partículas).
- **Reloj de tiempo real DS1302** (con pila CR2032): la Pi no tiene reloj propio y
  sin red arrancaría con la hora del último apagado. Conexión, a 3,3 V:
  VCC → pin 17, GND → pin 9, CLK → pin 11 (GPIO17), DAT → pin 13 (GPIO27),
  RST → pin 15 (GPIO22). Los pines se configuran en `config.py`.
- **DHT11 (Seeed Studio Grove, temperatura y humedad relativa):** SIG (amarillo) → pin 16
  (GPIO23), VCC (rojo) → **3,3 V, pin 1**, GND (negro) → pin 14; el hilo blanco (NC) queda
  aislado. **Nunca a 5 V:** el módulo trae su pull-up hacia VCC y la línea de datos quedaría a 5 V
  en el GPIO. No necesita divisor ni pull-up externo.

### Sensor DHT11 (driver del kernel)
El protocolo del DHT11 (pulsos de 26-70 µs) lo decodifica el driver `dht11` del kernel, que valida
el checksum y expone la medición en IIO; `sensors/dht11.py` solo lee esos archivos (sin bibliotecas
nuevas). El overlay usa GPIO4 por defecto, que es el pin del PPD42NS: hay que indicar `gpiopin=23`.
```bash
sudo cp /boot/firmware/config.txt ~/config.txt.respaldo
printf "\n# DHT11 (Grove): SIG en GPIO23 / pin 16\ndtoverlay=dht11,gpiopin=23\n" | sudo tee -a /boot/firmware/config.txt
sudo reboot
# Tras el reinicio:
lsmod | grep dht11                                     # módulo cargado
grep -H . /sys/bus/iio/devices/iio:device*/name        # dht11@17 -> config.DHT11_IIO_DIR
cat /sys/bus/iio/devices/iio:device0/in_temp_input     # m°C (p. ej. 22000)
cat /sys/bus/iio/devices/iio:device0/in_humidityrelative_input   # m%RH
```
Es normal que la primera lectura tras el arranque falle (`Error de entrada/salida`): el nodo lo
registra en el log y lo intenta de nuevo en el siguiente periodo.

### Reloj de tiempo real (DS1302)
`tools/rtc_ds1302.py` lee y escribe el DS1302 por GPIO (no usa I2C ni requiere
controlador del kernel). El RTC guarda la hora en UTC.
```bash
python3 -m tools.rtc_ds1302 leer       # hora del RTC frente a la del sistema
python3 -m tools.rtc_ds1302 guardar    # RTC <- sistema (solo con NTP sincronizado)

# Servicios: al arrancar sin internet, sistema <- RTC antes de que empiece la
# adquisición; cada hora, si hay NTP, RTC <- sistema (corrige su deriva).
sudo cp deploy/systemd/rtc-ds1302.service deploy/systemd/rtc-ds1302-guardar.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rtc-ds1302.service rtc-ds1302-guardar.timer
```
El DS1302 se desvía ~1–2 min al mes: conviene que la Pi tenga internet de vez en
cuando (p. ej. en casa) para que el temporizador lo corrija.

El hostname de la Pi debe ser `raspberrypi`: el gateway (app móvil) localiza el
broker como `raspberrypi.local`. Comprobación desde cualquier equipo de la WLAN:
```bash
hostnamectl hostname                    # en la Pi: raspberrypi
avahi-resolve -n raspberrypi.local      # nombre -> IP por mDNS
avahi-browse -rt _mqtt._tcp             # anuncio "Broker KI-1 en raspberrypi", puerto 1883
```

## Ejecución
```bash
python3 main.py                              # sensado real: MQTT + outbox_ki1.jsonl
python3 main.py --broker otro-equipo.local   # broker por nombre de dominio
python3 main.py --sink file                  # sin broker: solo outbox_ki1.jsonl
python3 main.py --simulate --window 3 --max 5    # prueba sin hardware
```

Con MQTT, cada documento se escribe también en `outbox_ki1.jsonl`: es el
registro de lo publicado por el nodo, que en la Fase 6 se compara con lo
recibido por el gateway por la clave `(sensor_id, observed_property, result_time)`.

Ver lo que publica el nodo (en otra terminal, en la Pi o en un equipo de la WLAN):
```bash
mosquitto_sub -h localhost -t 'vehiculo/#' -v
```

Validar semánticamente lo recibido por MQTT:
```bash
mosquitto_sub -h localhost -t 'vehiculo/#' -F '%p' -W 70 > recibido.jsonl
python3 -m tools.validate_jsonld recibido.jsonl --show
```

## Arranque automático (sesiones de horas en el vehículo)
```bash
sudo cp deploy/systemd/edge-node.service /etc/systemd/system/
# Adaptar el usuario y la ruta de la instalación (sin editar el archivo copiado):
sudo systemctl edit edge-node        # [Service] User=<usuario>  WorkingDirectory=<ruta del repo>
# Valores operativos opcionales (ver la sección siguiente):
sudo cp deploy/edge-node.env.example /etc/edge-node.env
sudo systemctl daemon-reload && sudo systemctl enable --now edge-node
journalctl -u edge-node -f
```
El servicio arranca después de Mosquitto. Si el broker no estuviera disponible,
el nodo sigue adquiriendo y entrega lo acumulado al conectarse.

## Configuración por entorno

Los valores operativos se sobrescriben con variables `EDGE_*` (en el servicio,
`EnvironmentFile=-/etc/edge-node.env`; plantilla en `deploy/edge-node.env.example`).
Se validan al arrancar: un valor no válido detiene el nodo con un mensaje que nombra la variable.

| Variable | Valor por defecto | Rango |
|---|---|---|
| `EDGE_MQTT_HOST` | `localhost` | nombre de host sin espacios |
| `EDGE_MQTT_PORT` | `1883` | 1–65535 |
| `EDGE_MQTT_CLIENT_ID` | `nodo_edge_moto_01` | 1–23 caracteres |
| `EDGE_OUTBOX_PATH` | `outbox_ki1.jsonl` | ruta, distinta de la de errores |
| `EDGE_ERRORS_PATH` | `outbox_ki1_errors.jsonl` | ruta |
| `EDGE_WINDOW_SECONDS` | `30` | (0, 600] |
| `EDGE_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `EDGE_SHUTDOWN_DRAIN_SECONDS` | `10` | [0, 120] |

Los IRIs del proyecto (`PROJECT_NS`, `VOCAB_NS`, `ID_BASE`) **no** son configurables: forman parte
del contrato y cambiarlos cambiaría la identidad de todas las observaciones.

## Robustez

- Un fallo al anotar, serializar, calcular el tópico o emitir una observación **no** detiene el
  nodo: se registra en el log y la observación cruda se guarda, con la etapa y el motivo, en
  `outbox_ki1_errors.jsonl` (JSON Lines con fsync); el bucle sigue con la siguiente
  (`core/pipeline.py`).
- Al parar el servicio (SIGTERM) o con Ctrl+C, el nodo deja de adquirir, procesa lo que queda en
  la cola durante `EDGE_SHUTDOWN_DRAIN_SECONDS` y cierra los sinks (MQTT espera la confirmación de
  lo pendiente).

## Pruebas y calidad (PC o Pi)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest                    # contrato KI-1 v2, identidad, semántica, M1 simulado, sinks, robustez, config
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Las pruebas del PPD42NS usan `gpiozero.pins.mock.MockFactory` con reloj inyectado: no necesitan
hardware ni esperan la ventana real.

## Parámetros críticos
Todos en `config.py` (namespace, sensor, ventana de muestreo, broker, QoS,
raíz de tópicos). El broker se indica siempre por nombre de dominio.
Antes de cada sesión de campo (Fase 6), poner la etiqueta de la ruta en
`PLATFORM["route_label"]` y seguir la lista de comprobación de campo
([`MCS_BACKEND/docs/operacion/CHECKLIST_CAMPO.md`](https://github.com/LeandroFreireGH/MCS_BACKEND/blob/master/docs/operacion/CHECKLIST_CAMPO.md), para imprimir): hotspot en 2,4 GHz,
`vcgencmd get_throttled` = `0x0` tras el arranque, copia del outbox al terminar.

## Calidad de las observaciones
Cada observación lleva `raw.quality_flag`:
- `ok`: medición válida.
- `stuck_low`: la señal estuvo en bajo toda la ventana sin ningún pulso (sensor
  desconectado o cable suelto). El LPO (≈ 1.0) no es válido y debe descartarse.

El DHT11 publica dos observaciones por lectura (`air_temperature` en `degree_celsius` y
`relative_humidity` en `percent_rh`) con el mismo `result_time`; su `raw.window_seconds` es la
duración real de la lectura (≈ 0,04 s), no el periodo. Una lectura que el driver rechaza (checksum
o tiempo agotado) no genera observación: queda en el log.

Tras arrancar la Pi o reiniciar el servicio, las mediciones empiezan después de un **periodo de
estabilización de 5 min** (o se descartan las de ese periodo): las primeras ventanas del PPD42NS
dan un LPO alto (transitorio de arranque del servicio, causa no determinada) y, tras un arranque,
el ajuste inicial de NTP desplaza el `result_time` de la primera ventana.

## Evidencia de alimentación (`raw.throttled`)
Cada observación lleva además `raw.throttled`: el valor de `vcgencmd get_throttled` al cerrar la
ventana (`"0x0"` con alimentación correcta; los bits 16–19 son acumulados desde el arranque). Es
evidencia, no cambia `quality_flag` (BL-51). Si `vcgencmd` no está disponible, el nodo sigue,
avisa una vez en el log y guarda `null` (`sensors/throttled.py`). El contrato KI-1 v2 no cambia:
`raw` admite campos libres.

## Nivel edge del experimento (replay)
Para medir el coste de la anotación en la Pi (ADR-004, hipótesis H3) sin GPIO ni pausas:
`tools/replay.py` lee una traza en JSONL canónico (exportada y ampliada en MCS_BACKEND),
reconstruye cada `Observation` y mide la transformación + serialización en el escenario
**BORDE** (`annotate` + `serialize`, KI-1 v2) o **BACKEND** (`raw_message` + `serialize`, mensaje
crudo de ADR-005, contrato `ki1-observation-raw`). `tools/experimento_edge.py` ejecuta la campaña
completa (calentamiento + 10 ejecuciones por escenario, alternadas, una por proceso) y aborta si
`get_throttled` ≠ `0x0` o la temperatura supera 70 °C. La medición sigue BL-60: dentro del bucle
medido solo se guardan marcas de tiempo y de CPU en memoria; el `@id`, `ts_utc`, los bytes y los CSV
se calculan y escriben después. La métrica principal (H3 y H1 en el edge) es la suma de los bloques
medidos dividida entre N; `total_ms / N` es secundaria. **No cambia el modo de producción:** el
replay no publica en MQTT ni escribe el outbox, y en campo el nodo siempre anota. Procedimiento en
la Pi: `ops/VERIFICACION_HARDWARE.md` §9; diseño y formato de los CSV: `PROTOCOLO_EXPERIMENTAL.md`
§6.2 y §7 (MCS_BACKEND).

```bash
python3 -m tools.replay --trace traza.jsonl --scenario BORDE \
    --run-id "$(python3 -c 'import uuid; print(uuid.uuid4())')" --out resultados/
python3 -m tools.experimento_edge --trace traza.jsonl --out resultados/ensayo \
    --repeticiones 2 --sin-control-hw          # ensayo en la PC (sin vcgencmd)
```
