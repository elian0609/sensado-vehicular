"""Iteración 5 — replay del nivel edge (ADR-004, PROTOCOLO_EXPERIMENTAL.md §6.2 y §7).

El replay lee una traza en JSONL canónico, reconstruye objetos Observation (contrato M1→M2) sin
GPIO ni pausas y mide, por observación, la transformación + serialización en cada escenario:
BORDE = M2 anota y serializa (KI-1 v2); BACKEND = serializa el mensaje crudo (ADR-005).
"""

import csv
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pyld import jsonld

from core.observation import Observation
from semantic.annotator import annotate, raw_message, serialize
from tests.conftest import CONTRACTS, load_json, make_observation, schema_errors
from tools import replay

RAIZ = Path(__file__).resolve().parents[1]
PILOTO = Path(__file__).parent / "fixtures" / "piloto"
TRAZA = PILOTO / "traza_base_sin_posicion.jsonl"
OUTBOX = PILOTO / "outbox_ki1_piloto.jsonl"

# PROTOCOLO_EXPERIMENTAL.md §7 (v1.3)
COLUMNAS_OBS = [
    "run_id", "escenario", "repeticion", "obs_idx", "observation_id",
    "annotate_serialize_us", "cpu_us", "bytes_ki1", "ts_utc",
]  # fmt: skip
COLUMNAS_EJECUCION = [
    "run_id", "escenario", "repeticion", "n_obs", "cpu_total_ms", "total_ms",
    "rss_inicio_mb", "rss_pico_mb", "temp_inicio_c", "temp_fin_c",
    "throttled_inicio", "throttled_fin", "inicio_utc", "fin_utc",
]  # fmt: skip


def _sin_red(url, options=None):
    raise AssertionError(f"la canonicalización no debe acceder a la red: {url}")


def _nquads(doc: dict) -> str:
    return jsonld.normalize(
        doc,
        {"algorithm": "URDNA2015", "format": "application/n-quads", "documentLoader": _sin_red},
    )


def _outbox() -> dict[str, dict]:
    docs = [json.loads(linea) for linea in OUTBOX.read_text(encoding="utf-8").splitlines()]
    return {d["@id"]: d for d in docs if d.get("@type") == "sosa:Observation"}


# --- Mensaje crudo (ADR-005) -----------------------------------------------------------


def test_mensaje_crudo_es_la_fixture_del_contrato():
    fixture = load_json(
        CONTRACTS / "fixtures/ki1-observation-raw/valid/telemetria-real-20261008.json"
    )
    crudo = raw_message(make_observation(), clock_source="gateway")
    assert crudo == fixture
    assert list(crudo) == list(fixture)  # mismo orden de claves
    assert not {"@context", "@type", "@id"} & crudo.keys()


def test_mensaje_crudo_no_modifica_la_observacion():
    obs = make_observation()
    raw_message(obs, clock_source="ntp")
    assert "clock_source" not in obs.raw


# --- Reconstrucción de la traza -------------------------------------------------------


def test_reconstruye_observation_y_clock_source_desde_el_nodo():
    nodo = json.loads(TRAZA.read_text(encoding="utf-8").splitlines()[0])
    obs, reloj = replay.observacion_de_nodo(nodo)
    assert isinstance(obs, Observation)
    assert obs.result_time == datetime(2026, 10, 19, 16, 36, 27, tzinfo=UTC)
    assert (obs.sensor_id, obs.observed_property, obs.unit) == (
        "ppd42ns_01", "low_pulse_occupancy_ratio", "ratio_0_1"
    )  # fmt: skip
    assert obs.value == 0.237675
    assert reloj == "ntp" and "clock_source" not in obs.raw
    # raw conserva el orden de la traza: el replay no supone el orden de claves de ningún sensor.
    assert list(obs.raw) == [k for k in nodo["raw"] if k != "clock_source"]


def test_ignora_los_campos_que_anade_la_app():
    nodo = json.loads(TRAZA.read_text(encoding="utf-8").splitlines()[0])
    con_posicion = {**nodo, "latitude": -2.9, "longitude": -78.98,
                    "position_source": "trayectoria_cercana"}  # fmt: skip
    assert replay.observacion_de_nodo(con_posicion) == replay.observacion_de_nodo(nodo)


def test_lee_la_traza_completa():
    observaciones = replay.leer_traza(TRAZA)
    assert len(observaciones) == 54


# --- Fidelidad: el replay reproduce lo que el edge emitió en campo --------------------


def test_modo_semantico_es_semanticamente_identico_a_lo_emitido_en_campo():
    emitidos = _outbox()
    observaciones = replay.leer_traza(TRAZA)
    assert len(emitidos) == len(observaciones) == 54
    for obs, reloj in observaciones:
        doc = annotate(obs, clock_source=reloj)
        campo = emitidos[doc["@id"]]
        assert _nquads(doc) == _nquads(campo), doc["@id"]
        assert doc["raw"] == campo["raw"]  # raw queda fuera de la expansión: se compara aparte


def test_modo_semantico_reproduce_el_tamano_y_el_documento_emitidos_en_campo():
    """La traza canónica pierde el orden de claves de raw: el mensaje reproducido tiene la misma
    longitud en bytes y el mismo documento JSON que el emitido; el orden de raw puede diferir."""
    emitidos = {json.loads(linea)["@id"]: linea
                for linea in OUTBOX.read_text(encoding="utf-8").splitlines()}  # fmt: skip
    for obs, reloj in replay.leer_traza(TRAZA):
        texto = serialize(annotate(obs, clock_source=reloj))
        campo = emitidos[json.loads(texto)["@id"]]
        assert len(texto.encode("utf-8")) == len(campo.encode("utf-8"))
        assert json.loads(texto) == json.loads(campo)


def _nodo_de_traza(obs: Observation, clock_source: str) -> dict:
    """Nodo KI-2 como lo exporta el backend: sin @context y con las claves ordenadas."""
    documento = {
        k: v for k, v in annotate(obs, clock_source=clock_source).items() if k != "@context"
    }
    return json.loads(json.dumps(documento, sort_keys=True))


def test_traza_mixta_reproduce_tamano_y_documento_de_cualquier_sensor():
    """Dos sensores con raw en su propio orden natural (ninguno coincide con el alfabético)."""
    observaciones = [
        make_observation(),
        make_observation(
            sensor_id="dht11_01",
            observed_property="air_temperature",
            value=22.0,
            unit="degree_celsius",
            raw={"gpio_pin_bcm": 23, "window_seconds": 0.043, "quality_flag": "ok"},
        ),
    ]
    for obs in observaciones:
        emitido = serialize(annotate(obs, clock_source="ntp"))
        nodo = _nodo_de_traza(obs, "ntp")
        reconstruida, reloj = replay.observacion_de_nodo(nodo)
        assert list(reconstruida.raw) == [k for k in nodo["raw"] if k != "clock_source"]
        for escenario in ("BORDE", "BACKEND"):
            texto = replay.transformar(reconstruida, reloj, escenario)
            original = replay.transformar(obs, "ntp", escenario)
            assert len(texto.encode("utf-8")) == len(original.encode("utf-8")), escenario
            assert json.loads(texto) == json.loads(original), escenario
        assert len(serialize(annotate(reconstruida, clock_source=reloj)).encode()) == len(
            emitido.encode()
        )


@pytest.mark.parametrize(
    ("escenario", "esquema"), [("BORDE", "ki1-observation"), ("BACKEND", "ki1-observation-raw")]
)
def test_cada_mensaje_valida_contra_su_contrato(escenario, esquema):
    for obs, reloj in replay.leer_traza(TRAZA):
        documento = json.loads(replay.transformar(obs, reloj, escenario))
        assert schema_errors(esquema, documento) == [], documento


def test_escenario_desconocido_es_error():
    obs, reloj = replay.leer_traza(TRAZA)[0]
    with pytest.raises(ValueError):
        replay.transformar(obs, reloj, "E")


# --- Medición y CSV (§7) ----------------------------------------------------------------


@pytest.mark.parametrize("escenario", ["BORDE", "BACKEND"])
def test_ejecucion_escribe_los_csv_con_las_columnas_del_protocolo(tmp_path, escenario):
    resumen = replay.main(["--trace", str(TRAZA), "--scenario", escenario, "--run-id",
                           "11111111-1111-1111-1111-111111111111", "--repeticion", "3",
                           "--out", str(tmp_path)])  # fmt: skip
    assert resumen == 0
    with (tmp_path / replay.ARCHIVO_OBS).open(encoding="utf-8") as f:
        lector = csv.DictReader(f)
        assert lector.fieldnames == COLUMNAS_OBS
        filas = list(lector)
    assert len(filas) == 54
    assert [int(f["obs_idx"]) for f in filas] == list(range(54))
    for fila, (obs, reloj) in zip(filas, replay.leer_traza(TRAZA), strict=True):
        assert fila["escenario"] == escenario and fila["repeticion"] == "3"
        assert float(fila["annotate_serialize_us"]) > 0 and float(fila["cpu_us"]) >= 0
        texto = replay.transformar(obs, reloj, escenario)
        assert int(fila["bytes_ki1"]) == len(texto.encode("utf-8"))
        assert fila["observation_id"].endswith(f"{obs.result_time:%Y%m%dT%H%M%SZ}")
    with (tmp_path / replay.ARCHIVO_EJECUCION).open(encoding="utf-8") as f:
        lector = csv.DictReader(f)
        assert lector.fieldnames == COLUMNAS_EJECUCION
        (ejecucion,) = list(lector)
    assert ejecucion["n_obs"] == "54"
    assert float(ejecucion["total_ms"]) > 0 and float(ejecucion["cpu_total_ms"]) >= 0
    assert float(ejecucion["rss_pico_mb"]) >= float(ejecucion["rss_inicio_mb"]) > 0


def test_bytes_borde_mayores_que_backend(tmp_path):
    obs, reloj = replay.leer_traza(TRAZA)[0]
    borde = len(replay.transformar(obs, reloj, "BORDE").encode())
    backend = len(replay.transformar(obs, reloj, "BACKEND").encode())
    assert borde > backend


def test_csv_se_anade_sin_repetir_cabecera(tmp_path):
    for repeticion in ("1", "2"):
        replay.main(["--trace", str(TRAZA), "--scenario", "BORDE", "--run-id",
                     f"0000000{repeticion}-0000-0000-0000-000000000000",
                     "--repeticion", repeticion, "--out", str(tmp_path)])  # fmt: skip
    lineas = (tmp_path / replay.ARCHIVO_OBS).read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 1 + 2 * 54
    assert lineas.count(",".join(COLUMNAS_OBS)) == 1


# --- Aislamiento del modo de producción ----------------------------------------------


def test_el_replay_no_publica_en_mqtt_ni_escribe_el_outbox(tmp_path):
    """En un intérprete limpio: tras el replay no se ha cargado ningún sink ni paho, y en el
    directorio de trabajo no aparece ningún outbox."""
    codigo = (
        "import runpy, sys\n"
        f"sys.argv = ['replay', '--trace', {str(TRAZA)!r}, '--scenario', 'BORDE', "
        f"'--run-id', '22222222-2222-2222-2222-222222222222', '--out', {str(tmp_path / 'out')!r}]\n"
        "try:\n"
        "    runpy.run_module('tools.replay', run_name='__main__')\n"
        "except SystemExit as e:\n"
        "    assert e.code in (0, None), e.code\n"
        "cargados = [m for m in sys.modules if m.startswith(('sinks', 'paho', 'gpiozero'))]\n"
        "assert not cargados, cargados\n"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo], cwd=tmp_path, capture_output=True, text=True,
        env={"PYTHONPATH": str(RAIZ), "PATH": "/usr/bin:/bin"},
    )  # fmt: skip
    assert resultado.returncode == 0, resultado.stderr
    assert not list(tmp_path.glob("outbox*"))
    assert (tmp_path / "out" / replay.ARCHIVO_OBS).exists()
