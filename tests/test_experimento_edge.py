"""Iteración 5 — campaña del nivel edge (PROTOCOLO_EXPERIMENTAL.md §6.2 y §7).

Calentamiento descartado + N ejecuciones por escenario, alternadas, cada una en un proceso nuevo;
aborta si get_throttled ≠ 0x0 o la temperatura supera el umbral.
"""

import csv
import json
from pathlib import Path

import pytest

from tools import experimento_edge as ee
from tools import replay

TRAZA = Path(__file__).parent / "fixtures" / "piloto" / "traza_base_sin_posicion.jsonl"

# PROTOCOLO_EXPERIMENTAL.md §7
COLUMNAS_EJECUCIONES = [
    "run_id", "nivel", "escenario", "repeticion", "orden", "descartada", "motivo",
    "traza_sha256", "commit", "inicio_utc", "fin_utc",
]  # fmt: skip


def _leer(ruta: Path) -> tuple[list[str], list[dict]]:
    with ruta.open(encoding="utf-8") as f:
        lector = csv.DictReader(f)
        return lector.fieldnames, list(lector)


def test_plan_alterna_escenarios_con_calentamiento_por_escenario():
    plan = ee.plan(["BORDE", "BACKEND"], repeticiones=2, calentamiento=1)
    assert [(p.escenario, p.repeticion) for p in plan] == [
        ("BORDE", 0), ("BACKEND", 0), ("BORDE", 1), ("BACKEND", 1), ("BORDE", 2), ("BACKEND", 2)
    ]  # fmt: skip
    assert [p.orden for p in plan] == list(range(1, 7))
    assert [p.descartada for p in plan] == [True, True, False, False, False, False]


def test_campana_de_ensayo_en_procesos_nuevos(tmp_path, capsys):
    """2 + 2 ejecuciones (más un calentamiento por escenario) con la traza piloto, sin los
    sensores de la Pi (en la PC no hay vcgencmd)."""
    codigo = ee.main(["--trace", str(TRAZA), "--out", str(tmp_path), "--repeticiones", "2",
                      "--sin-control-hw"])  # fmt: skip
    assert codigo == 0

    columnas, ejecuciones = _leer(tmp_path / ee.ARCHIVO_EJECUCIONES)
    assert columnas == COLUMNAS_EJECUCIONES
    assert len(ejecuciones) == 6
    assert [e["escenario"] for e in ejecuciones] == ["BORDE", "BACKEND"] * 3
    assert [e["descartada"] for e in ejecuciones] == ["true", "true"] + ["false"] * 4
    assert {e["nivel"] for e in ejecuciones} == {"edge"}
    assert len({e["run_id"] for e in ejecuciones}) == 6
    sha = json.loads((tmp_path / ee.ARCHIVO_META).read_text())["traza"]["sha256"]
    assert {e["traza_sha256"] for e in ejecuciones} == {sha}

    columnas, observaciones = _leer(tmp_path / replay.ARCHIVO_OBS)
    assert len(observaciones) == 6 * 54
    columnas, por_ejecucion = _leer(tmp_path / replay.ARCHIVO_EJECUCION)
    assert len(por_ejecucion) == 6
    assert {p["run_id"] for p in por_ejecucion} == {e["run_id"] for e in ejecuciones}

    meta = json.loads((tmp_path / ee.ARCHIVO_META).read_text())
    assert meta["parametros"]["repeticiones"] == 2 and meta["parametros"]["control_hw"] is False
    assert {"commit", "entorno", "traza", "inicio_utc", "fin_utc"} <= meta.keys()
    salida = capsys.readouterr().out
    assert "BORDE" in salida and "BACKEND" in salida and "p95" in salida


@pytest.mark.parametrize(
    ("throttled", "temperatura", "motivo"),
    [
        ("0x50000", 45.0, "get_throttled"),
        ("0x0", 75.0, "temperatura"),
        (None, 45.0, "get_throttled"),  # sin poder comprobarlo no se mide
        ("0x0", None, "temperatura"),
    ],
)
def test_aborta_si_la_pi_no_esta_en_condiciones(tmp_path, throttled, temperatura, motivo):
    codigo = ee.campana(
        TRAZA, tmp_path, repeticiones=1, calentamiento=1, control_hw=True,
        leer_throttled=lambda: throttled, leer_temperatura=lambda: temperatura,
        ejecutar=lambda *a, **k: pytest.fail("no debía ejecutarse ninguna medición"),
    )  # fmt: skip
    assert codigo == ee.CODIGO_ABORTADA
    _, ejecuciones = _leer(tmp_path / ee.ARCHIVO_EJECUCIONES)
    assert ejecuciones[0]["descartada"] == "true"
    assert motivo in ejecuciones[0]["motivo"]


def test_aborta_a_mitad_si_cambia_el_estado(tmp_path):
    lecturas = iter(["0x0", "0x0", "0x50005"])
    ejecutadas = []

    def ejecutar(paso, *args, **kwargs):
        ejecutadas.append(paso)

    codigo = ee.campana(
        TRAZA, tmp_path, repeticiones=2, calentamiento=1, control_hw=True,
        leer_throttled=lambda: next(lecturas), leer_temperatura=lambda: 45.0, ejecutar=ejecutar,
    )  # fmt: skip
    assert codigo == ee.CODIGO_ABORTADA
    assert len(ejecutadas) == 2  # la tercera no llega a lanzarse
    _, ejecuciones = _leer(tmp_path / ee.ARCHIVO_EJECUCIONES)
    assert ejecuciones[-1]["descartada"] == "true" and "0x50005" in ejecuciones[-1]["motivo"]


def test_temperatura_inicial_por_encima_de_50_no_arranca(tmp_path):
    codigo = ee.campana(
        TRAZA, tmp_path, repeticiones=1, calentamiento=1, control_hw=True,
        leer_throttled=lambda: "0x0", leer_temperatura=lambda: 55.0,
        ejecutar=lambda *a, **k: pytest.fail("no debía ejecutarse"),
    )  # fmt: skip
    assert codigo == ee.CODIGO_ABORTADA
    _, ejecuciones = _leer(tmp_path / ee.ARCHIVO_EJECUCIONES)
    assert "50" in ejecuciones[0]["motivo"]


def test_umbral_de_temperatura_por_defecto():
    assert ee.TEMP_MAX_C == 70.0 and ee.TEMP_INICIO_MAX_C == 50.0
