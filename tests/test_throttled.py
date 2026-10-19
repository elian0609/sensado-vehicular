"""BL-51 (Iteración 4b): evidencia de alimentación en raw.throttled.

Al cerrar cada ventana el edge guarda el valor de `vcgencmd get_throttled` en hexadecimal
(p. ej. "0x0"). El lector se inyecta: en las pruebas es falso; en la Pi lanza vcgencmd. Si no
está disponible, el nodo sigue, avisa una sola vez y guarda raw.throttled = null.
"""

import logging
import subprocess
from datetime import UTC, datetime, timedelta

import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from semantic.annotator import annotate, serialize
from sensors.ppd42ns import PPD42NSSensor
from sensors.throttled import ThrottledProbe, leer_vcgencmd
from tests.conftest import schema_errors

PIN = 4
T0 = datetime(2026, 10, 19, 16, 36, 27, tzinfo=UTC)


class Reloj:
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


def _sensor(reloj, throttled, ventana=30.0):
    def pausa(segundos):
        reloj.t += segundos

    return PPD42NSSensor(
        "ppd42ns_01",
        PIN,
        ventana,
        "ambient_air_at_device",
        monotonic=reloj.monotonic,
        sleep=pausa,
        now=reloj.now,
        throttled=throttled,
    )


# --- Lector de vcgencmd --------------------------------------------------------------


class Completado:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.returncode = stdout, returncode


@pytest.mark.parametrize(
    ("salida", "esperado"),
    [
        ("throttled=0x0\n", "0x0"),
        ("throttled=0x50005\n", "0x50005"),
        ("throttled=0X50000", "0x50000"),
    ],
)
def test_vcgencmd_se_normaliza_a_hexadecimal(salida, esperado):
    llamadas = []

    def run(args, **kwargs):
        llamadas.append((args, kwargs))
        return Completado(salida)

    assert leer_vcgencmd(run=run) == esperado
    args, kwargs = llamadas[0]
    assert args == ["vcgencmd", "get_throttled"]
    assert kwargs["timeout"] <= 1.0  # nunca bloquea más de 1 s


@pytest.mark.parametrize(
    "fallo",
    [
        FileNotFoundError("vcgencmd"),
        subprocess.TimeoutExpired("vcgencmd", 1.0),
        PermissionError("/dev/vcio"),
    ],
)
def test_vcgencmd_no_disponible_lanza_error_propio(fallo):
    def run(args, **kwargs):
        raise fallo

    with pytest.raises(OSError):
        leer_vcgencmd(run=run)


@pytest.mark.parametrize("salida", ["", "throttled=abc", "error: VCHI", "0x0"])
def test_salida_inesperada_es_error(salida):
    with pytest.raises(ValueError):
        leer_vcgencmd(run=lambda args, **kw: Completado(salida))


def test_codigo_de_salida_distinto_de_cero_es_error():
    with pytest.raises(OSError):
        leer_vcgencmd(run=lambda args, **kw: Completado("throttled=0x0", returncode=255))


# --- Sonda con aviso único ------------------------------------------------------------


def test_sonda_devuelve_el_valor_del_lector():
    assert ThrottledProbe(lambda: "0x0").read() == "0x0"


def test_sonda_sin_lector_disponible_devuelve_none_y_avisa_una_vez(caplog):
    def lector():
        raise FileNotFoundError("vcgencmd")

    sonda = ThrottledProbe(lector)
    with caplog.at_level(logging.WARNING):
        assert [sonda.read() for _ in range(5)] == [None] * 5
    avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(avisos) == 1
    assert "throttled" in avisos[0].getMessage()


def test_sonda_con_salida_inesperada_devuelve_none():
    def lector():
        raise ValueError("salida inesperada")

    assert ThrottledProbe(lector).read() is None


# --- En el sensor ---------------------------------------------------------------------


def test_cada_ventana_guarda_el_valor_en_raw(pin):
    valores = iter(["0x0", "0x50005"])
    sensor = _sensor(Reloj(), lambda: next(valores))
    (a,) = sensor.read()
    (b,) = sensor.read()
    sensor.close()
    assert a.raw["throttled"] == "0x0"
    assert b.raw["throttled"] == "0x50005"


def test_sin_lector_disponible_el_nodo_sigue_y_guarda_null(pin, caplog):
    def lector():
        raise FileNotFoundError("vcgencmd")

    sensor = _sensor(Reloj(), lector)
    with caplog.at_level(logging.WARNING):
        observaciones = [sensor.read()[0] for _ in range(3)]
    sensor.close()
    assert [o.raw["throttled"] for o in observaciones] == [None] * 3
    assert all(o.raw["quality_flag"] == "ok" for o in observaciones)
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


def test_la_lectura_no_altera_la_ventana(pin):
    """El lector se llama al cerrar la ventana, después de medirla: aunque tarde, la
    duración y el LPO no cambian, y result_time es el fin de la ventana."""
    reloj = Reloj()

    def lector_lento():
        reloj.t += 0.8  # lectura lenta (el límite real es 1 s)
        return "0x0"

    sensor = _sensor(reloj, lector_lento)
    (obs,) = sensor.read()
    sensor.close()
    assert obs.raw["window_seconds"] == 30.0
    assert obs.result_time == T0 + timedelta(seconds=30)


def test_la_lectura_se_hace_fuera_del_cerrojo_de_los_pulsos(pin):
    """Mientras se lee, los flancos del GPIO se pueden registrar (no se bloquean)."""
    reloj = Reloj()
    estado = {}

    def lector():
        estado["cerrojo_libre"] = sensor._lock.acquire(blocking=False)
        if estado["cerrojo_libre"]:
            sensor._lock.release()
        return "0x0"

    sensor = _sensor(reloj, lector)
    sensor.read()
    sensor.close()
    assert estado["cerrojo_libre"] is True


@pytest.mark.parametrize("valor", ["0x0", None])
def test_la_salida_sigue_validando_contra_ki1_observation_v2(pin, valor):
    sensor = _sensor(Reloj(), lambda: valor)
    (obs,) = sensor.read()
    sensor.close()
    documento = annotate(obs, clock_source="ntp")
    assert documento["raw"]["throttled"] == valor
    assert schema_errors("ki1-observation", documento) == []
    assert '"throttled":' in serialize(documento)
