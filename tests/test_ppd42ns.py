"""M1 del PPD42NS con GPIO simulado (gpiozero MockFactory) y reloj inyectado.

El reloj y la pausa de la ventana se inyectan: los pulsos se simulan dentro de la
"pausa" avanzando un reloj falso, así que el LPO esperado es exacto y la prueba
no espera la ventana real.
"""

from datetime import UTC, datetime, timedelta

import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from sensors.ppd42ns import PPD42NSSensor, lpo_ratio

PIN = 4
T0 = datetime(2026, 10, 8, 16, 17, 9, tzinfo=UTC)


class RelojFalso:
    def __init__(self):
        self.t = 100.0

    def monotonic(self) -> float:
        return self.t

    def now(self) -> datetime:
        return T0 + timedelta(seconds=self.t - 100.0)


@pytest.fixture
def pin():
    Device.pin_factory = MockFactory()
    mock = Device.pin_factory.pin(PIN)
    mock.drive_high()
    yield mock
    Device.pin_factory.close()


def _sensor(reloj, eventos, ventana=3.0):
    """eventos: [(segundos desde el último evento, 'bajo' | 'alto')] durante la ventana."""

    def pausa(segundos):
        inicio = reloj.t
        for dt, nivel in eventos:
            reloj.t += dt
            pin = Device.pin_factory.pin(PIN)
            pin.drive_low() if nivel == "bajo" else pin.drive_high()
        reloj.t = inicio + segundos

    return PPD42NSSensor(
        "ppd42ns_01",
        PIN,
        ventana,
        "ambient_air_at_device",
        monotonic=reloj.monotonic,
        sleep=pausa,
        now=reloj.now,
    )


def test_lpo_de_pulsos_conocidos(pin):
    reloj = RelojFalso()
    eventos = [
        (0.5, "bajo"), (0.25, "alto"),   # 0,25 s en bajo
        (0.5, "bajo"), (0.5, "alto"),    # 0,5 s
        (0.5, "bajo"), (0.125, "alto"),  # 0,125 s
    ]  # fmt: skip
    sensor = _sensor(reloj, eventos)
    (obs,) = sensor.read()
    sensor.close()
    assert obs.value == 0.291667  # 0,875 / 3, redondeado a 6 decimales
    assert obs.raw["pulse_count"] == 3
    assert obs.raw["low_time_seconds"] == 0.875
    assert obs.raw["window_seconds"] == 3.0
    assert obs.raw["quality_flag"] == "ok"
    assert obs.observed_property == "low_pulse_occupancy_ratio"
    assert obs.unit == "ratio_0_1"


def test_result_time_es_el_fin_de_la_ventana(pin):
    reloj = RelojFalso()
    sensor = _sensor(reloj, [(1.0, "bajo"), (0.2, "alto")])
    (obs,) = sensor.read()
    sensor.close()
    assert obs.result_time == T0 + timedelta(seconds=3)
    assert obs.result_time.tzinfo is not None


def test_pulso_abierto_al_cierre_cuenta_hasta_el_fin_de_la_ventana(pin):
    reloj = RelojFalso()
    sensor = _sensor(reloj, [(2.5, "bajo")])
    (obs,) = sensor.read()
    sensor.close()
    assert obs.value == round(0.5 / 3, 6)
    assert obs.raw["pulse_count"] == 0  # un pulso no cerrado no se cuenta
    assert obs.raw["quality_flag"] == "ok"  # LPO < 0,99


def test_stuck_low_con_cero_pulsos_y_lpo_maximo(pin):
    reloj = RelojFalso()
    pin.drive_low()  # sensor desconectado: el pin queda en bajo toda la ventana
    sensor = _sensor(reloj, [])
    (obs,) = sensor.read()
    sensor.close()
    assert obs.value == 1.0
    assert obs.raw["pulse_count"] == 0
    assert obs.raw["quality_flag"] == "stuck_low"


def test_sin_stuck_low_si_hubo_pulsos_aunque_el_lpo_sea_alto(pin):
    reloj = RelojFalso()
    pin.drive_low()
    sensor = _sensor(reloj, [(0.01, "alto"), (0.001, "bajo")])
    (obs,) = sensor.read()
    sensor.close()
    assert obs.value >= 0.99
    assert obs.raw["pulse_count"] == 1
    assert obs.raw["quality_flag"] == "ok"


def test_sin_pulsos_y_sin_bajo_no_es_stuck_low(pin):
    reloj = RelojFalso()
    sensor = _sensor(reloj, [])
    (obs,) = sensor.read()
    sensor.close()
    assert obs.value == 0.0
    assert obs.raw["quality_flag"] == "ok"


@pytest.mark.parametrize(
    ("bajo", "ventana", "esperado"),
    [
        (0.875, 3.0, 0.291667),
        (4.0004, 30.0, 0.133347),
        (31.0, 30.0, 1.0),  # se limita a 1
        (-0.1, 30.0, 0.0),  # se limita a 0
        (1.0, 3.0, 0.333333),
    ],
)
def test_lpo_ratio_se_limita_a_0_1_y_redondea_a_6_decimales(bajo, ventana, esperado):
    assert lpo_ratio(bajo, ventana) == esperado


def test_lpo_ratio_rechaza_ventana_no_positiva():
    with pytest.raises(ValueError):
        lpo_ratio(1.0, 0.0)
