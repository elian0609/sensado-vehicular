"""
MqttSink: publica los documentos JSON-LD de KI-1 en el broker MQTT.

El broker se localiza por nombre de dominio (config.MQTT_BROKER_HOST), no por
dirección IP: la resolución la hace el sistema operativo (DNS o mDNS/.local) y
se vuelve a intentar en cada reconexión, de modo que un cambio de IP no exige
modificar la configuración.

La conexión es asíncrona: si el broker aún no está disponible al arrancar, el
nodo sigue adquiriendo y los mensajes QoS 1 quedan en la cola del cliente
hasta que la conexión se establece.
"""
import logging
import socket
import threading
import time
from typing import Callable, Optional

import paho.mqtt.client as mqtt

import config
from sinks.base import Ki1Sink
from sinks.topics import gateway_time_topic

log = logging.getLogger("edge_node.mqtt")


def resolve(host: str, port: int) -> list:
    """Direcciones IP a las que resuelve el nombre del broker (trazabilidad)."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def _new_client(client_id: str) -> mqtt.Client:
    if hasattr(mqtt, "CallbackAPIVersion"):                    # paho-mqtt >= 2.0
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id,
                           protocol=mqtt.MQTTv311)
    return mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)  # paho 1.x


class MqttSink(Ki1Sink):
    def __init__(self, host: str = None, port: int = None,
                 on_gateway_time: Optional[Callable[[bytes], object]] = None):
        """on_gateway_time: recibe la hora que publica el gateway (core/clock.py)."""
        self.host = host or config.MQTT_BROKER_HOST
        self.port = port or config.MQTT_BROKER_PORT
        self.qos = config.MQTT_QOS
        self._on_gateway_time = on_gateway_time
        self._connected = threading.Event()
        self._closing = False

        self._client = _new_client(config.MQTT_CLIENT_ID)
        if config.MQTT_USERNAME:
            self._client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
        self._client.max_queued_messages_set(0)                 # cola sin límite
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        try:
            log.info("Broker %s:%d resuelve a %s", self.host, self.port,
                     ", ".join(resolve(self.host, self.port)))
        except socket.gaierror as e:
            log.warning("No se pudo resolver %s (%s); se reintentará al conectar",
                        self.host, e)

        self._client.connect_async(self.host, self.port,
                                   keepalive=config.MQTT_KEEPALIVE)
        self._client.loop_start()

    # paho 2.x entrega reason_code como objeto; paho 1.x como entero.
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if getattr(reason_code, "is_failure", reason_code != 0):
            log.error("Conexión rechazada por el broker: %s", reason_code)
            return
        self._connected.set()
        log.info("Conectado al broker %s:%d", self.host, self.port)
        if self._on_gateway_time:
            client.subscribe(gateway_time_topic(), qos=0)

    def _on_message(self, client, userdata, message):
        if message.topic == gateway_time_topic() and self._on_gateway_time:
            try:
                self._on_gateway_time(message.payload)
            except Exception:
                log.exception("Fallo al procesar la hora del gateway")

    def _on_disconnect(self, client, userdata, *args):
        self._connected.clear()
        if self._closing:
            log.info("Desconexión ordenada del broker")
        else:
            log.warning("Conexión con el broker perdida; reintentando")

    def wait_connected(self, timeout: float) -> bool:
        return self._connected.wait(timeout)

    def emit(self, payload: str, topic: str, retain: bool = False) -> None:
        info = self._client.publish(topic, payload, qos=self.qos, retain=retain)
        if info.rc not in (mqtt.MQTT_ERR_SUCCESS, mqtt.MQTT_ERR_NO_CONN):
            log.error("Publicación rechazada (rc=%s) en %s", info.rc, topic)

    def close(self, timeout: float = 5.0) -> None:
        """Espera a que el broker confirme lo pendiente antes de desconectar."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and (self._pending() or self._client.want_write()):
            time.sleep(0.1)
        if self._pending():
            log.warning("%d mensajes sin confirmar al cerrar", self._pending())
        self._closing = True
        self._client.disconnect()
        self._client.loop_stop()

    def _pending(self) -> int:
        return len(getattr(self._client, "_out_messages", {}))
