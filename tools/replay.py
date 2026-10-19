"""Replay del nivel edge (ADR-004; PROTOCOLO_EXPERIMENTAL.md §6.2 y §7; Iteración 5).

Lee una traza en JSONL canónico (exportada o ampliada en MCS_BACKEND), reconstruye cada
observación como `Observation` (contrato M1→M2) sin GPIO ni pausas y mide, para cada una, la
transformación + serialización del escenario:

    BORDE    M2 anota y serializa el documento KI-1 v2 (annotate + serialize)
    BACKEND  se serializa el mensaje crudo de KI-1 (raw_message + serialize, ADR-005)

Por observación: tiempo de pared (`perf_counter_ns`), CPU del proceso (`process_time_ns`) y bytes
UTF-8 del mensaje. Por ejecución: CPU y tiempo totales del bucle de medición, RSS al empezar y
pico (`/proc/self/status`), temperatura y `get_throttled` al empezar y al terminar. La lectura de
la traza y la reconstrucción de los objetos quedan fuera de la medición.

No publica en MQTT ni escribe el outbox: no importa `sinks` ni el GPIO. Añade filas a
<out>/metricas_edge.csv y <out>/metricas_edge_ejecucion.csv (cabecera solo si el archivo es nuevo).
Lo lanza tools/experimento_edge.py, una ejecución por proceso; también se puede usar suelto:

    python3 -m tools.replay --trace traza_ampliada.jsonl --scenario BORDE \\
        --run-id "$(python3 -c 'import uuid; print(uuid.uuid4())')" --out resultados/
"""

from __future__ import annotations

import argparse
import csv
import json
import resource
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.observation import Observation
from semantic.annotator import annotate, raw_message, serialize
from semantic.identity import observation_id
from sensors.throttled import ThrottledProbe

ESCENARIOS = ("BORDE", "BACKEND")
ARCHIVO_OBS = "metricas_edge.csv"
ARCHIVO_EJECUCION = "metricas_edge_ejecucion.csv"

# PROTOCOLO_EXPERIMENTAL.md §7 (v1.3): no cambiar sin cambiar el protocolo.
COLUMNAS_OBS = (
    "run_id", "escenario", "repeticion", "obs_idx", "observation_id",
    "annotate_serialize_us", "cpu_us", "bytes_ki1", "ts_utc",
)  # fmt: skip
COLUMNAS_EJECUCION = (
    "run_id", "escenario", "repeticion", "n_obs", "cpu_total_ms", "total_ms",
    "rss_inicio_mb", "rss_pico_mb", "temp_inicio_c", "temp_fin_c",
    "throttled_inicio", "throttled_fin", "inicio_utc", "fin_utc",
)  # fmt: skip

# Orden de raw que emite M1 (sensors/ppd42ns.py); la traza canónica lo tiene en orden alfabético.
ORDEN_RAW = (
    "pulse_count", "low_time_seconds", "window_seconds", "gpio_pin_bcm",
    "quality_flag", "throttled",
)  # fmt: skip
CAMPOS_DE_LA_APP = ("latitude", "longitude", "position_source")
TEMPERATURA = Path("/sys/class/thermal/thermal_zone0/temp")


def _iso(instante: datetime) -> str:
    return instante.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def observacion_de_nodo(nodo: dict[str, Any]) -> tuple[Observation, str | None]:
    """Nodo KI-2 de la traza → (Observation de M1, clock_source).

    Se ignoran @id/@type (los vuelve a generar M2) y los campos que añade la app (posición).
    clock_source sale de raw porque annotate() lo añade de nuevo; el resto de raw recupera el
    orden de M1 para que el mensaje sea byte a byte el que emitió el nodo en campo.
    """
    raw = dict(nodo.get("raw") or {})
    reloj = raw.pop("clock_source", None)
    ordenado = {k: raw[k] for k in ORDEN_RAW if k in raw}
    ordenado.update({k: raw[k] for k in sorted(raw) if k not in ordenado})
    instante = datetime.fromisoformat(nodo["result_time"].replace("Z", "+00:00")).astimezone(UTC)
    obs = Observation(
        sensor_id=nodo["sensor_id"],
        observed_property=nodo["observed_property"],
        value=nodo["value"],
        unit=nodo["unit"],
        result_time=instante,
        feature_of_interest=nodo["feature_of_interest"],
        raw=ordenado,
    )
    return obs, reloj


def leer_traza(ruta: Path) -> list[tuple[Observation, str | None]]:
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    return [observacion_de_nodo(json.loads(linea)) for linea in lineas if linea]


def transformar(obs: Observation, clock_source: str | None, escenario: str) -> str:
    """El bloque que se mide: transformación + serialización del escenario."""
    if escenario == "BORDE":
        return serialize(annotate(obs, clock_source=clock_source))
    if escenario == "BACKEND":
        return serialize(raw_message(obs, clock_source=clock_source))
    raise ValueError(f"escenario desconocido: {escenario!r} (BORDE o BACKEND)")


def _status_mb(clave: str) -> float | None:
    """VmRSS / VmHWM de /proc/self/status, en MiB."""
    try:
        for linea in Path("/proc/self/status").read_text().splitlines():
            if linea.startswith(clave + ":"):
                return int(linea.split()[1]) / 1024
    except OSError:
        pass
    return None


def rss_mb() -> float | None:
    return _status_mb("VmRSS")


def rss_pico_mb() -> float | None:
    pico = _status_mb("VmHWM")
    if pico is None:  # sin /proc: getrusage (KiB en Linux)
        pico = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return pico


def leer_temperatura() -> float | None:
    try:
        return int(TEMPERATURA.read_text().strip()) / 1000
    except (OSError, ValueError):
        return None


def _escribir(ruta: Path, columnas: tuple[str, ...], filas: list[dict[str, Any]]) -> None:
    nuevo = not ruta.exists()
    with ruta.open("a", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas, lineterminator="\n")
        if nuevo:
            escritor.writeheader()
        escritor.writerows(filas)


def _numero(valor: float | None, decimales: int = 3) -> str:
    return "" if valor is None else f"{valor:.{decimales}f}"


def ejecutar(
    observaciones: list[tuple[Observation, str | None]],
    escenario: str,
    run_id: str,
    repeticion: int,
    *,
    leer_throttled=None,
    leer_temp=leer_temperatura,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Mide una ejecución completa; devuelve las filas por observación y la de la ejecución."""
    if escenario not in ESCENARIOS:
        raise ValueError(f"escenario desconocido: {escenario!r} (BORDE o BACKEND)")
    leer_throttled = leer_throttled or ThrottledProbe().read
    inicio = datetime.now(UTC)
    throttled_inicio, temp_inicio, rss_inicio = leer_throttled(), leer_temp(), rss_mb()

    filas = []
    total_t0, total_c0 = time.perf_counter_ns(), time.process_time_ns()
    for idx, (obs, reloj) in enumerate(observaciones):
        t0, c0 = time.perf_counter_ns(), time.process_time_ns()
        texto = transformar(obs, reloj, escenario)
        c1, t1 = time.process_time_ns(), time.perf_counter_ns()
        filas.append(
            {
                "run_id": run_id,
                "escenario": escenario,
                "repeticion": repeticion,
                "obs_idx": idx,
                "observation_id": observation_id(
                    obs.sensor_id, obs.observed_property, obs.result_time
                ),
                "annotate_serialize_us": f"{(t1 - t0) / 1000:.3f}",
                "cpu_us": f"{(c1 - c0) / 1000:.3f}",
                "bytes_ki1": len(texto.encode("utf-8")),
                "ts_utc": _iso(datetime.now(UTC)),
            }
        )
    total_c1, total_t1 = time.process_time_ns(), time.perf_counter_ns()

    ejecucion = {
        "run_id": run_id,
        "escenario": escenario,
        "repeticion": repeticion,
        "n_obs": len(filas),
        "cpu_total_ms": f"{(total_c1 - total_c0) / 1e6:.3f}",
        "total_ms": f"{(total_t1 - total_t0) / 1e6:.3f}",
        "rss_inicio_mb": _numero(rss_inicio),
        "rss_pico_mb": _numero(rss_pico_mb()),
        "temp_inicio_c": _numero(temp_inicio, 1),
        "temp_fin_c": _numero(leer_temp(), 1),
        "throttled_inicio": throttled_inicio or "",
        "throttled_fin": leer_throttled() or "",
        "inicio_utc": _iso(inicio),
        "fin_utc": _iso(datetime.now(UTC)),
    }
    return filas, ejecucion


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trace", required=True, type=Path, help="traza en JSONL canónico")
    ap.add_argument("--scenario", required=True, choices=ESCENARIOS)
    ap.add_argument("--run-id", required=True, type=lambda v: str(uuid.UUID(v)))
    ap.add_argument("--repeticion", type=int, default=1, help="0 = calentamiento")
    ap.add_argument("--out", required=True, type=Path, help="directorio de resultados")
    args = ap.parse_args(argv)

    observaciones = leer_traza(args.trace)
    filas, ejecucion = ejecutar(observaciones, args.scenario, args.run_id, args.repeticion)
    args.out.mkdir(parents=True, exist_ok=True)
    _escribir(args.out / ARCHIVO_OBS, COLUMNAS_OBS, filas)
    _escribir(args.out / ARCHIVO_EJECUCION, COLUMNAS_EJECUCION, [ejecucion])
    return 0


if __name__ == "__main__":
    sys.exit(main())
