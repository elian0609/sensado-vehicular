"""Regla de identidad de la observación (ADR-002), única fuente: semantic/identity.py."""

from datetime import datetime, timedelta, timezone

import pytest

from semantic.identity import observation_id
from tests.conftest import RESULT_TIME, make_observation

ESPERADO = "obs/ppd42ns_01/low_pulse_occupancy_ratio/20261008T161739Z"


def test_id_relativo_exacto_segun_adr002():
    assert observation_id("ppd42ns_01", "low_pulse_occupancy_ratio", RESULT_TIME) == ESPERADO


def test_rechaza_result_time_sin_zona_horaria():
    with pytest.raises(ValueError):
        observation_id("ppd42ns_01", "low_pulse_occupancy_ratio", datetime(2026, 10, 8, 16, 17, 39))


def test_convierte_desfase_horario_a_utc():
    guayaquil = timezone(timedelta(hours=-5))
    local = datetime(2026, 10, 8, 11, 17, 39, tzinfo=guayaquil)
    assert observation_id("ppd42ns_01", "low_pulse_occupancy_ratio", local) == ESPERADO


def test_descarta_fracciones_de_segundo_como_el_result_time_emitido():
    con_microsegundos = RESULT_TIME.replace(microsecond=999_999)
    assert observation_id("ppd42ns_01", "low_pulse_occupancy_ratio", con_microsegundos) == ESPERADO


def test_determinista_y_estable_ante_objetos_distintos_con_los_mismos_datos():
    a, b = make_observation(), make_observation(raw={"otro": "raw"})
    assert a is not b
    ids = {observation_id(o.sensor_id, o.observed_property, o.result_time) for o in (a, b, a)}
    assert ids == {ESPERADO}


def test_distinto_instante_distinto_id():
    siguiente = RESULT_TIME + timedelta(seconds=30)
    assert observation_id("ppd42ns_01", "low_pulse_occupancy_ratio", siguiente) != ESPERADO


@pytest.mark.parametrize("segmento", ["", "con espacio", "a/b", "#x"])
def test_rechaza_segmentos_no_validos_para_una_iri_relativa(segmento):
    with pytest.raises(ValueError):
        observation_id(segmento, "low_pulse_occupancy_ratio", RESULT_TIME)
