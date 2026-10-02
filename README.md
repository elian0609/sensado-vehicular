# Nodo Edge (H2) — M1 + M2 y publicación en KI-1

```
PPD42NS --GPIO4--> M1 (sensors/ppd42ns.py, hilo propio, ventana 30 s)
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

## Contrato MQTT de KI-1

| Mensaje | Tópico | QoS | Retain |
|---|---|---|---|
| Telemetría | `vehiculo/sensor/{sensor_id}/observacion` | 1 | no |
| Registro de plataforma | `vehiculo/plataforma/registro` | 1 | sí |
| Registro de propiedad | `vehiculo/propiedad/{property_name}/registro` | 1 | sí |
| Registro de sensor | `vehiculo/sensor/{sensor_id}/registro` | 1 | sí |

- Broker: puerto 1883, MQTT v3.1.1, sin autenticación (WLAN privada del hotspot).
- La carga útil de cada mensaje es el documento JSON-LD 1.1 del DIV-3.
- El gateway debe suscribirse a `vehiculo/#` con QoS 1, un `client_id` fijo y
  `clean_session = false`, para que el broker le guarde lo publicado mientras
  esté desconectado.
- Los registros pueden llegar repetidos (se reenvían al volver a suscribirse):
  el gateway debe tratarlos como actualización por identificador, no como alta.

## Instalación en la Raspberry Pi
```bash
cd ~ && git clone https://github.com/elian0609/sensado-vehicular.git
cd sensado-vehicular
sudo apt install -y python3-gpiozero python3-lgpio python3-paho-mqtt \
                    mosquitto mosquitto-clients avahi-daemon
pip3 install pyld --break-system-packages      # solo para validar

# Broker de KI-1 (escucha en la WLAN, persistencia cada 60 s)
sudo cp deploy/mosquitto/ki1.conf /etc/mosquitto/conf.d/ki1.conf
sudo systemctl enable --now mosquitto && sudo systemctl restart mosquitto

# Anuncio del broker por DNS-SD (_mqtt._tcp) para que el gateway lo descubra
sudo cp deploy/avahi/ki1-mqtt.service /etc/avahi/services/ki1-mqtt.service
sudo systemctl reload avahi-daemon
```

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
sudo systemctl daemon-reload && sudo systemctl enable --now edge-node
journalctl -u edge-node -f
```
El servicio arranca después de Mosquitto. Si el broker no estuviera disponible,
el nodo sigue adquiriendo y entrega lo acumulado al conectarse.

## Parámetros críticos
Todos en `config.py` (namespace, sensor, ventana de muestreo, broker, QoS,
raíz de tópicos). El broker se indica siempre por nombre de dominio.
