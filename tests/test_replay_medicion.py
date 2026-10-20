"""Iteración 7 — BL-60: la instrumentación del replay queda fuera de la región medida.

Dentro del bucle medido solo se toman marcas de tiempo y de CPU y se guardan en memoria; el @id de
cada fila, su marca ts_utc y la escritura del CSV ocurren después. La métrica principal del nivel
edge (H1 en el edge y H3) es la suma de los bloques medidos / N; con la instrumentación fuera,
total_ms / N casi coincide con ella.
"""

from pathlib import Path

import pytest

from tools import replay

TRAZA = Path(__file__).parent / "fixtures" / "piloto" / "traza_base_sin_posicion.jsonl"


def _sin_hw():
    return {"leer_throttled": lambda: None, "leer_temp": lambda: None}


@pytest.fixture
def eventos(monkeypatch):
    """Registra el orden de las llamadas relevantes durante una ejecución."""
    registro: list[str] = []
    transformar, observation_id, iso = replay.transformar, replay.observation_id, replay._iso

    def espia_transformar(*args, **kwargs):
        registro.append("medido")
        return transformar(*args, **kwargs)

    def espia_id(*args, **kwargs):
        registro.append("id")
        return observation_id(*args, **kwargs)

    def espia_iso(*args, **kwargs):
        registro.append("ts")
        return iso(*args, **kwargs)

    monkeypatch.setattr(replay, "transformar", espia_transformar)
    monkeypatch.setattr(replay, "observation_id", espia_id)
    monkeypatch.setattr(replay, "_iso", espia_iso)
    return registro


@pytest.mark.parametrize("escenario", replay.ESCENARIOS)
def test_el_id_y_las_marcas_de_tiempo_se_calculan_despues_del_bucle_medido(eventos, escenario):
    observaciones = replay.leer_traza(TRAZA)
    replay.ejecutar(observaciones, escenario, "r", 1, **_sin_hw())
    ultimo_medido = max(i for i, e in enumerate(eventos) if e == "medido")
    primeros = [i for i, e in enumerate(eventos) if e in ("id", "ts")]
    assert eventos.count("medido") == len(observaciones)
    assert primeros and min(primeros) > ultimo_medido, eventos[:10]


def test_el_csv_se_escribe_al_terminar_la_ejecucion(monkeypatch, tmp_path, eventos):
    escribir = replay._escribir

    def espia_escribir(*args, **kwargs):
        eventos.append("csv")
        return escribir(*args, **kwargs)

    monkeypatch.setattr(replay, "_escribir", espia_escribir)
    replay.main(["--trace", str(TRAZA), "--scenario", "BORDE", "--run-id",
                 "44444444-4444-4444-4444-444444444444", "--out", str(tmp_path)])  # fmt: skip
    ultimo_medido = max(i for i, e in enumerate(eventos) if e == "medido")
    assert min(i for i, e in enumerate(eventos) if e == "csv") > ultimo_medido
    assert eventos.count("csv") == 2  # metricas_edge.csv y metricas_edge_ejecucion.csv


def test_las_filas_conservan_el_formato_del_protocolo(tmp_path):
    filas, ejecucion = replay.ejecutar(replay.leer_traza(TRAZA), "BORDE", "r", 2, **_sin_hw())
    assert [list(f) for f in filas[:1]] == [list(replay.COLUMNAS_OBS)]
    assert [f["obs_idx"] for f in filas] == list(range(54))
    assert all(f["ts_utc"].endswith("Z") for f in filas)
    instantes = [f["ts_utc"] for f in filas]
    assert instantes == sorted(instantes)  # marcas derivadas del reloj monótono, en orden
    assert ejecucion["inicio_utc"] <= instantes[0] <= instantes[-1] <= ejecucion["fin_utc"]


def test_total_por_ejecucion_casi_igual_a_la_suma_de_los_bloques():
    """Con la instrumentación fuera del bucle, el sobrecoste del bucle es pequeño frente al
    bloque medido (antes de BL-60: +43 % en BORDE en la PC y +44 % en la Pi)."""
    observaciones = replay.leer_traza(TRAZA) * 20  # 1080 observaciones
    replay.ejecutar(observaciones, "BORDE", "r", 0, **_sin_hw())  # calentamiento
    filas, ejecucion = replay.ejecutar(observaciones, "BORDE", "r", 1, **_sin_hw())
    bloques_us = sum(float(f["annotate_serialize_us"]) for f in filas)
    total_us = float(ejecucion["total_ms"]) * 1000
    assert total_us >= bloques_us
    assert (total_us - bloques_us) / bloques_us < 0.25
