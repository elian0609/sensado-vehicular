"""
Orquestador del Nodo Edge (H2): ejecuta M1 y M2 y emite hacia KI-1.

  M1 (un hilo por sensor) --cola interna--> M2 (hilo principal) --> KI-1

Cada sensor muestrea con su propia ventana, en su propio hilo, de modo que un
sensor de ventana larga (PPD42NS, 30 s) no bloquea a otro más rápido.

Uso:
  python3 main.py                        # hardware real: MQTT (KI-1) + outbox_ki1.jsonl
  python3 main.py --broker otro.local    # broker por nombre de dominio
  python3 main.py --sink file            # sin broker: solo outbox_ki1.jsonl
  python3 main.py --simulate             # sin hardware: GPIO simulado

Valores operativos por entorno (EDGE_MQTT_HOST, EDGE_WINDOW_SECONDS, ...): ver
config.py y deploy/edge-node.env.example.
"""

import argparse
import logging
import queue
import random
import signal
import sys
import threading
import time

import config
from core.clock import ClockSync
from core.pipeline import Pipeline, run_loop
from semantic.annotator import serialize
from semantic.registry import registration_documents
from sinks.base import FanOutSink, JsonlFileSink
from sinks.topics import topic_for

log = logging.getLogger("edge_node")


def enable_simulation(pin: int) -> None:
    """GPIO simulado: genera pulsos bajos aleatorios en el pin del PPD42NS."""
    from gpiozero import Device
    from gpiozero.pins.mock import MockFactory

    Device.pin_factory = MockFactory()
    mock_pin = Device.pin_factory.pin(pin)

    def pulses():
        while True:
            mock_pin.drive_high()
            time.sleep(random.uniform(0.05, 0.5))
            mock_pin.drive_low()
            time.sleep(random.uniform(0.005, 0.04))

    threading.Thread(target=pulses, daemon=True).start()


def build_sensors():
    from sensors.ppd42ns import PPD42NSSensor

    return [
        PPD42NSSensor(
            config.PPD42NS_SENSOR_ID,
            config.PPD42NS_GPIO_BCM,
            config.PPD42NS_WINDOW_SECONDS,
            config.DEFAULT_FEATURE_OF_INTEREST,
        ),
        # Nuevo sensor = una línea aquí (p. ej. DHT11Sensor(...)).
    ]


def acquisition_loop(sensor, out: queue.Queue, stop: threading.Event):
    while not stop.is_set():
        try:
            for obs in sensor.read():
                out.put(obs)
        except Exception:
            # Criterio: el fallo de un sensor no detiene al resto del nodo.
            log.exception("Fallo de lectura en %s; se reintenta", sensor.sensor_id)
            time.sleep(1)


def emit_registrations(sink) -> None:
    """Metadatos de registro: una sola vez al iniciar, antes de la telemetría.
    Un registro que falla se registra en el log y no impide arrancar el nodo."""
    for doc in registration_documents():
        try:
            topic, retain = topic_for(doc)
            sink.emit(serialize(doc), topic, retain)
            log.info("KI-1 <- registro %s -> %s (retain)", doc["@type"], topic)
        except Exception:
            log.exception("No se pudo emitir el registro %s", doc.get("@type"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--window", type=float, help="sobrescribe la ventana (solo pruebas)")
    ap.add_argument("--max", type=int, help="detener tras N observaciones (solo pruebas)")
    ap.add_argument(
        "--sink",
        choices=["mqtt", "file"],
        default="mqtt",
        help="transporte de KI-1 (por defecto: mqtt, con copia en el outbox)",
    )
    ap.add_argument("--broker", help="nombre de dominio del broker (sobrescribe config)")
    args = ap.parse_args()

    try:
        config.apply_environment()  # EDGE_* (deploy/edge-node.env.example)
    except config.ConfigError as e:
        sys.exit(f"Configuración no válida: {e}")

    logging.basicConfig(
        level=config.LOG_LEVEL, stream=sys.stderr, format="%(asctime)s %(levelname)s %(message)s"
    )
    if args.window:
        config.PPD42NS_WINDOW_SECONDS = args.window
    if args.simulate:
        enable_simulation(config.PPD42NS_GPIO_BCM)

    sensors = build_sensors()
    clock = ClockSync()
    outbox = JsonlFileSink(config.OUTBOX_PATH)
    errors = JsonlFileSink(config.ERRORS_PATH)
    if args.sink == "mqtt":
        from sinks.mqtt import MqttSink

        # La bandeja se escribe en paralelo: respaldo y referencia de lo publicado.
        # Sin internet, la hora del gateway corrige el reloj del nodo.
        sink = FanOutSink(outbox, MqttSink(host=args.broker, on_gateway_time=clock.on_gateway_time))
    else:
        sink = outbox

    q, stop = queue.Queue(), threading.Event()
    # SIGTERM (systemd) y Ctrl+C: dejar de adquirir y vaciar la cola antes de salir.
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    emit_registrations(sink)

    for s in sensors:
        threading.Thread(target=acquisition_loop, args=(s, q, stop), daemon=True).start()
        log.info("Sensor %s activo (ventana %.1f s)", s.sensor_id, s.sample_window_seconds)

    pipeline = Pipeline(sink=sink, errors=errors, clock_source=clock.source)
    try:
        run_loop(q, stop, pipeline, config.SHUTDOWN_DRAIN_SECONDS, max_emitted=args.max)
    finally:
        stop.set()
        log.info(
            "Fin: %d observaciones emitidas, %d con error (ver %s)",
            pipeline.emitted,
            pipeline.failed,
            config.ERRORS_PATH,
        )
        for s in sensors:
            s.close()
        sink.close()
        errors.close()


if __name__ == "__main__":
    main()
