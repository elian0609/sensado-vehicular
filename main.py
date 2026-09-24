"""
Orquestador del Nodo Edge (H2): ejecuta M1 y M2 y emite hacia KI-1.

  M1 (un hilo por sensor) --cola interna--> M2 (hilo principal) --> KI-1

Cada sensor muestrea con su propia ventana, en su propio hilo, de modo que un
sensor de ventana larga (PPD42NS, 30 s) no bloquea a otro más rápido.

Uso:
  python3 main.py              # hardware real (Raspberry Pi)
  python3 main.py --simulate   # sin hardware: GPIO simulado (gpiozero MockFactory)
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
from semantic.annotator import annotate, serialize
from semantic.registry import registration_documents
from sinks.base import JsonlFileSink

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
        PPD42NSSensor(config.PPD42NS_SENSOR_ID, config.PPD42NS_GPIO_BCM,
                      config.PPD42NS_WINDOW_SECONDS,
                      config.DEFAULT_FEATURE_OF_INTEREST),
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--window", type=float, help="sobrescribe la ventana (solo pruebas)")
    ap.add_argument("--max", type=int, help="detener tras N observaciones (solo pruebas)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(message)s")
    if args.window:
        config.PPD42NS_WINDOW_SECONDS = args.window
    if args.simulate:
        enable_simulation(config.PPD42NS_GPIO_BCM)

    sensors = build_sensors()
    sink = JsonlFileSink(config.OUTBOX_PATH)
    q, stop = queue.Queue(), threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    # Metadatos de registro: una sola vez al iniciar, antes de la telemetría.
    for doc in registration_documents():
        sink.emit(serialize(doc))
        log.info("KI-1 <- registro %s", doc["@type"])

    for s in sensors:
        threading.Thread(target=acquisition_loop, args=(s, q, stop), daemon=True).start()
        log.info("Sensor %s activo (ventana %.1f s)", s.sensor_id, s.sample_window_seconds)

    emitted = 0
    try:
        while not stop.is_set():
            try:
                obs = q.get(timeout=1)
            except queue.Empty:
                continue
            payload = serialize(annotate(obs))          # M2
            sink.emit(payload)                          # KI-1
            emitted += 1
            log.info("KI-1 <- %s %s=%s (%d bytes)", obs.sensor_id,
                     obs.observed_property, obs.value, len(payload.encode()))
            if args.max and emitted >= args.max:
                break
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        for s in sensors:
            s.close()
        sink.close()


if __name__ == "__main__":
    main()
