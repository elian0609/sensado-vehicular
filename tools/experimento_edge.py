"""Campaña del nivel edge (ADR-004; PROTOCOLO_EXPERIMENTAL.md §6.2 y §7; Iteración 5).

Ejecuta, con la misma traza, `calentamiento` ejecuciones descartadas y `repeticiones` válidas por
escenario, alternadas (BORDE, BACKEND, BORDE, …), **cada una en un proceso nuevo**
(`python3 -m tools.replay`). Antes de cada ejecución comprueba la Pi:

  - `get_throttled` debe ser `0x0` (sin bajo voltaje ni limitación desde el arranque);
  - la temperatura no debe superar TEMP_MAX_C (70 °C) y, antes de la primera, TEMP_INICIO_MAX_C
    (50 °C, §6.2 paso 3).

Si una comprobación falla, o no se puede hacer, la campaña se aborta y la ejecución queda
registrada como descartada con el motivo. Umbral de 70 °C: la Pi 3B empieza a bajar la frecuencia
de la CPU a partir de 80 °C (firmware); 10 °C de margen garantizan que ninguna medición se haga con
la frecuencia limitada, y la alternancia reparte el calentamiento entre escenarios. Cualquier
limitación real además activa un bit de `get_throttled`.

Salida en --out (debe estar vacío): ejecuciones.csv (§7), metricas_edge.csv y
metricas_edge_ejecucion.csv (los escribe cada replay) y campana.meta.json (hash de la traza,
commit, entorno, parámetros). Al terminar imprime la mediana y el p95 por escenario, solo como
comprobación: el análisis formal es la Iteración 7.

    python3 -m tools.experimento_edge --trace traza_ampliada.jsonl --out resultados/20261020/
    python3 -m tools.experimento_edge ... --repeticiones 2 --sin-control-hw   # ensayo en la PC
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sensors.throttled import ThrottledProbe
from tools import replay

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVO_EJECUCIONES = "ejecuciones.csv"
ARCHIVO_META = "campana.meta.json"
CODIGO_ABORTADA = 2
TEMP_MAX_C = 70.0
TEMP_INICIO_MAX_C = 50.0

# PROTOCOLO_EXPERIMENTAL.md §7: no cambiar sin cambiar el protocolo.
COLUMNAS_EJECUCIONES = (
    "run_id", "nivel", "escenario", "repeticion", "orden", "descartada", "motivo",
    "traza_sha256", "commit", "inicio_utc", "fin_utc",
)  # fmt: skip


@dataclass(frozen=True)
class Paso:
    escenario: str
    repeticion: int  # 0..calentamiento-1 = calentamiento
    orden: int
    descartada: bool


def plan(escenarios: list[str], repeticiones: int, calentamiento: int) -> list[Paso]:
    """Calentamiento por escenario y repeticiones alternadas, en el orden dado."""
    pasos, orden = [], 0
    for repeticion in range(calentamiento + repeticiones):
        for escenario in escenarios:
            orden += 1
            pasos.append(Paso(escenario, repeticion, orden, repeticion < calentamiento))
    return pasos


def _ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _commit() -> str | None:
    try:
        salida = subprocess.run(
            ["git", "-C", str(RAIZ), "describe", "--always", "--dirty", "--abbrev=40"],
            capture_output=True, text=True, check=True,
        )  # fmt: skip
    except (OSError, subprocess.CalledProcessError):
        return None
    return salida.stdout.strip()


def _leer(ruta: str) -> str | None:
    try:
        return Path(ruta).read_text(encoding="utf-8").strip("\x00\n ")
    except OSError:
        return None


def entorno() -> dict[str, Any]:
    """Lo que §4 pide registrar y se puede leer sin privilegios."""
    so = None
    for linea in (_leer("/etc/os-release") or "").splitlines():
        if linea.startswith("PRETTY_NAME="):
            so = linea.split("=", 1)[1].strip('"')
    return {
        "modelo": _leer("/proc/device-tree/model"),
        "so": so,
        "kernel": platform.release(),
        "maquina": platform.machine(),
        "python": platform.python_version(),
        "gobernador_cpu": _leer("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
    }


def ejecutar_proceso(paso: Paso, traza: Path, out: Path, run_id: str) -> None:
    """Una ejecución en un intérprete nuevo (sin cachés de la anterior)."""
    subprocess.run(
        [sys.executable, "-m", "tools.replay", "--trace", str(traza.resolve()),
         "--scenario", paso.escenario, "--run-id", run_id,
         "--repeticion", str(paso.repeticion), "--out", str(out.resolve())],
        cwd=RAIZ, check=True,
    )  # fmt: skip


def _comprobar(
    primera: bool,
    leer_throttled: Callable[[], str | None],
    leer_temperatura: Callable[[], float | None],
    temp_max: float,
    temp_inicio_max: float,
) -> str | None:
    """None si la Pi está en condiciones; si no, el motivo."""
    throttled = leer_throttled()
    if throttled != "0x0":
        return f"get_throttled = {throttled or 'no disponible'} (se exige 0x0)"
    temperatura = leer_temperatura()
    if temperatura is None:
        return "temperatura no disponible"
    limite = temp_inicio_max if primera else temp_max
    if temperatura > limite:
        momento = "antes de la primera ejecución" if primera else "entre ejecuciones"
        return f"temperatura {temperatura:.1f} °C > {limite:.0f} °C ({momento})"
    return None


def _fila(
    paso: Paso,
    run_id: str,
    sha: str,
    commit: str | None,
    inicio: str,
    fin: str,
    descartada: bool,
    motivo: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "nivel": "edge",
        "escenario": paso.escenario,
        "repeticion": paso.repeticion,
        "orden": paso.orden,
        "descartada": "true" if descartada else "false",
        "motivo": motivo,
        "traza_sha256": sha,
        "commit": commit or "",
        "inicio_utc": inicio,
        "fin_utc": fin,
    }


def _escribir_ejecuciones(out: Path, filas: list[dict[str, Any]]) -> None:
    with (out / ARCHIVO_EJECUCIONES).open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS_EJECUCIONES, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


def resumen(out: Path, filas: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Mediana y p95 por escenario de las ejecuciones válidas (comprobación rápida)."""
    validas = {f["run_id"] for f in filas if f["descartada"] == "false"}
    ruta = out / replay.ARCHIVO_OBS
    if not validas or not ruta.exists():
        return {}
    por_escenario: dict[str, dict[str, list[float]]] = {}
    with ruta.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            if fila["run_id"] in validas:
                datos = por_escenario.setdefault(fila["escenario"], {"us": [], "cpu": [], "b": []})
                datos["us"].append(float(fila["annotate_serialize_us"]))
                datos["cpu"].append(float(fila["cpu_us"]))
                datos["b"].append(float(fila["bytes_ki1"]))

    def p95(valores: list[float]) -> float:
        return statistics.quantiles(valores, n=20)[18] if len(valores) > 1 else valores[0]

    return {
        escenario: {
            "n": len(d["us"]),
            "us_mediana": statistics.median(d["us"]),
            "us_p95": p95(d["us"]),
            "cpu_us_mediana": statistics.median(d["cpu"]),
            "bytes_mediana": statistics.median(d["b"]),
        }
        for escenario, d in por_escenario.items()
    }


def campana(
    traza: Path,
    out: Path,
    *,
    repeticiones: int = 10,
    calentamiento: int = 1,
    escenarios: tuple[str, ...] = replay.ESCENARIOS,
    control_hw: bool = True,
    temp_max: float = TEMP_MAX_C,
    temp_inicio_max: float = TEMP_INICIO_MAX_C,
    leer_throttled: Callable[[], str | None] | None = None,
    leer_temperatura: Callable[[], float | None] | None = None,
    ejecutar: Callable[..., None] = ejecutar_proceso,
) -> int:
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise SystemExit(f"{out} no está vacío: cada campaña va en su propio directorio")
    leer_throttled = leer_throttled or ThrottledProbe().read
    leer_temperatura = leer_temperatura or replay.leer_temperatura
    sha, commit, inicio_campana = _sha256(traza), _commit(), _ahora()
    meta: dict[str, Any] = {
        "protocolo": "PROTOCOLO_EXPERIMENTAL.md §6.2 y §7 (v1.3)",
        "traza": {
            "archivo": traza.name,
            "sha256": sha,
            "n_obs": sum(1 for linea in traza.read_text(encoding="utf-8").splitlines() if linea),
        },
        "commit": commit,
        "entorno": entorno(),
        "parametros": {
            "escenarios": list(escenarios),
            "repeticiones": repeticiones,
            "calentamiento": calentamiento,
            "control_hw": control_hw,
            "temp_max_c": temp_max,
            "temp_inicio_max_c": temp_inicio_max,
        },
        "inicio_utc": inicio_campana,
    }

    filas: list[dict[str, Any]] = []
    pasos = plan(list(escenarios), repeticiones, calentamiento)
    codigo = 0
    for i, paso in enumerate(pasos):
        run_id = str(uuid.uuid4())
        if control_hw:
            motivo = _comprobar(i == 0, leer_throttled, leer_temperatura, temp_max, temp_inicio_max)
            if motivo:
                filas.append(
                    _fila(
                        paso, run_id, sha, commit, _ahora(), _ahora(), True, f"abortada: {motivo}"
                    )
                )
                codigo = CODIGO_ABORTADA
                break
        inicio = _ahora()
        try:
            ejecutar(paso, traza, out, run_id)
        except subprocess.CalledProcessError as exc:
            filas.append(
                _fila(
                    paso,
                    run_id,
                    sha,
                    commit,
                    inicio,
                    _ahora(),
                    True,
                    f"abortada: el replay terminó con código {exc.returncode}",
                )
            )
            codigo = CODIGO_ABORTADA
            break
        filas.append(
            _fila(
                paso,
                run_id,
                sha,
                commit,
                inicio,
                _ahora(),
                paso.descartada,
                "calentamiento" if paso.descartada else "",
            )
        )
    else:
        if control_hw:  # el estado al terminar también cuenta para la última ejecución
            motivo = _comprobar(False, leer_throttled, leer_temperatura, temp_max, temp_inicio_max)
            if motivo:
                filas[-1].update(descartada="true", motivo=f"invalidada al terminar: {motivo}")
                codigo = CODIGO_ABORTADA

    _escribir_ejecuciones(out, filas)
    meta.update(
        fin_utc=_ahora(),
        estado="completa" if codigo == 0 else "abortada",
        ejecuciones=len(filas),
        resumen=resumen(out, filas),
    )
    (out / ARCHIVO_META).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _imprimir(meta, filas)
    return codigo


def _imprimir(meta: dict[str, Any], filas: list[dict[str, Any]]) -> None:
    print(
        f"Campaña {meta['estado']}: {len(filas)} ejecuciones · traza {meta['traza']['sha256'][:12]}"
    )
    if filas and filas[-1]["motivo"].startswith(("abortada", "invalidada")):
        print(f"  {filas[-1]['motivo']}")
    print("Escenario  n_obs   mediana_us   p95_us   cpu_mediana_us   bytes_mediana")
    for escenario, r in meta["resumen"].items():
        print(
            f"{escenario:<9} {r['n']:>6} {r['us_mediana']:>11.1f} {r['us_p95']:>8.1f} "
            f"{r['cpu_us_mediana']:>15.1f} {r['bytes_mediana']:>14.0f}"
        )
    print("(solo comprobación; el análisis estadístico es la Iteración 7)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trace", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path, help="directorio vacío de la campaña")
    ap.add_argument(
        "--repeticiones", type=int, default=10, help="por escenario (sin calentamiento)"
    )
    ap.add_argument("--calentamiento", type=int, default=1, help="descartadas por escenario")
    ap.add_argument("--orden", default="BORDE,BACKEND", help="escenarios en orden de alternancia")
    ap.add_argument("--temp-max", type=float, default=TEMP_MAX_C)
    ap.add_argument(
        "--sin-control-hw",
        action="store_true",
        help="no comprobar get_throttled ni temperatura (solo ensayos fuera de la Pi)",
    )
    args = ap.parse_args(argv)
    escenarios = tuple(e.strip() for e in args.orden.split(","))
    if set(escenarios) != set(replay.ESCENARIOS):
        ap.error("--orden debe contener BORDE y BACKEND")
    return campana(
        args.trace, args.out, repeticiones=args.repeticiones, calentamiento=args.calentamiento,
        escenarios=escenarios, control_hw=not args.sin_control_hw, temp_max=args.temp_max,
    )  # fmt: skip


if __name__ == "__main__":
    sys.exit(main())
