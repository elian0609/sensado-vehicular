"""M1 del Grove DHT11 con el directorio IIO del driver del kernel simulado y reloj inyectado.

El driver `dht11` expone la última medición en in_temp_input (m°C) e in_humidityrelative_input
(m%RH); aquí son archivos en tmp_path. La pausa del periodo y el reloj se inyectan: la prueba no
espera el periodo real.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory

import config
import main
from semantic.annotator import annotate, raw_message, serialize
from semantic.registry import registration_documents
from sensors.dht11 import DHT11Sensor
from sinks.topics import topic_for
from tests.conftest import schema_errors
from tests.test_contract_ki1 import edge_checks

PIN = 23
PERIODO = 30.0
T0 = datetime(2026, 10, 27, 17, 40, 0, tzinfo=UTC)


class RelojFalso:
    def __init__(self, duracion_lectura: float = 0.043):
        self.t = 100.0
        self.pausas: list[float] = []
        self.duracion_lectura = duracion_lectura
        self._lecturas = 0

    def monotonic(self) -> float:
        # La segunda consulta (fin de la lectura) avanza la duración de la transacción del driver.
        self._lecturas += 1
        if self._lecturas % 2 == 0:
            self.t += self.duracion_lectura
        return self.t

    def sleep(self, segundos: float) -> None:
        self.pausas.append(segundos)
        self.t += segundos

    def now(self) -> datetime:
        return T0 + timedelta(seconds=self.t - 100.0)


def _iio(directorio, temperatura="22000", humedad="37000"):
    (directorio / "in_temp_input").write_text(temperatura + "\n")
    (directorio / "in_humidityrelative_input").write_text(humedad + "\n")
    return directorio


def _sensor(iio_dir, reloj):
    return DHT11Sensor(
        "dht11_01",
        PIN,
        PERIODO,
        "ambient_air_at_device",
        iio_dir,
        monotonic=reloj.monotonic,
        sleep=reloj.sleep,
        now=reloj.now,
    )


def test_una_lectura_produce_temperatura_y_humedad_de_la_misma_medicion(tmp_path):
    reloj = RelojFalso()
    temperatura, humedad = _sensor(_iio(tmp_path), reloj).read()

    assert (temperatura.observed_property, temperatura.unit) == (
        "air_temperature",
        "degree_celsius",
    )
    assert (humedad.observed_property, humedad.unit) == ("relative_humidity", "percent_rh")
    assert (temperatura.value, humedad.value) == (22.0, 37.0)  # m°C y m%RH del driver
    assert temperatura.result_time == humedad.result_time
    assert temperatura.result_time.tzinfo is not None
    for obs in (temperatura, humedad):
        assert obs.sensor_id == "dht11_01"
        assert obs.feature_of_interest == "ambient_air_at_device"


def test_espera_su_periodo_antes_de_leer(tmp_path):
    reloj = RelojFalso()
    sensor = _sensor(_iio(tmp_path), reloj)
    assert sensor.sample_window_seconds == PERIODO
    observaciones = sensor.read()
    assert reloj.pausas == [PERIODO]
    # result_time es el instante de la medición, al final del periodo y de la lectura.
    assert observaciones[0].result_time == T0 + timedelta(seconds=PERIODO + 0.043)


def test_raw_con_la_duracion_real_de_la_lectura_no_el_periodo(tmp_path):
    (temperatura, humedad) = _sensor(_iio(tmp_path), RelojFalso(duracion_lectura=0.043)).read()
    assert temperatura.raw == humedad.raw
    assert temperatura.raw["window_seconds"] == pytest.approx(0.043)
    assert temperatura.raw["gpio_pin_bcm"] == PIN
    assert temperatura.raw["quality_flag"] == "ok"
    assert set(temperatura.raw) == {"gpio_pin_bcm", "window_seconds", "quality_flag"}


def test_window_seconds_nunca_es_cero(tmp_path):
    """El contrato exige window_seconds > 0 (exclusiveMinimum) y la app lo usa para ubicar la
    observación (BL-53): una lectura instantánea en el reloj falso no puede publicarse como 0."""
    (temperatura, _) = _sensor(_iio(tmp_path), RelojFalso(duracion_lectura=0.0)).read()
    assert temperatura.raw["window_seconds"] > 0


def test_temperatura_bajo_cero(tmp_path):
    (temperatura, _) = _sensor(_iio(tmp_path, temperatura="-2000"), RelojFalso()).read()
    assert temperatura.value == -2.0


def test_el_constructor_no_toca_el_hardware(tmp_path):
    """Un DHT11 ausente (sin overlay) no impide arrancar el nodo: el fallo llega en read()."""
    _sensor(tmp_path / "no-existe", RelojFalso())


def test_un_fallo_del_driver_se_propaga_y_no_genera_observaciones(tmp_path):
    """EIO/ETIMEDOUT del driver llegan como OSError: acquisition_loop los registra y reintenta."""
    (tmp_path / "in_temp_input").write_text("22000\n")  # falta la humedad
    with pytest.raises(OSError):
        _sensor(tmp_path, RelojFalso()).read()


def test_las_observaciones_anotadas_cumplen_el_contrato_ki1_v2_y_se_expanden_a_rdf(tmp_path):
    for obs in _sensor(_iio(tmp_path), RelojFalso()).read():
        documento = json.loads(serialize(annotate(obs, clock_source="ntp")))
        assert edge_checks("ki1-observation", documento) == [], obs.observed_property
        assert documento["@id"] == f"obs/dht11_01/{obs.observed_property}/20261027T174030Z"
        assert schema_errors("ki1-observation-raw", raw_message(obs, clock_source="ntp")) == []


# --- Registro en el nodo (config.py y build_sensors() de main.py) -----------------------------


def test_el_dht11_y_sus_propiedades_se_publican_como_registros_validos():
    documentos = registration_documents()
    sensores = {d["sensor_id"]: d for d in documentos if d["@type"] == "sosa:Sensor"}
    propiedades = {
        d["property_name"]: d for d in documentos if d["@type"] == "sosa:ObservableProperty"
    }
    assert sensores["dht11_01"]["sensor_model"] == "DHT11"
    assert sensores["dht11_01"]["hosted_by"] == config.PLATFORM["vehicle_id"]
    assert propiedades["air_temperature"]["unit"] == "degree_celsius"
    assert propiedades["relative_humidity"]["unit"] == "percent_rh"
    for documento in (
        sensores["dht11_01"],
        propiedades["air_temperature"],
        propiedades["relative_humidity"],
    ):
        recibido = json.loads(serialize(documento))
        esquema = (
            "ki1-registro-sensor"
            if documento["@type"] == "sosa:Sensor"
            else "ki1-registro-property"
        )
        assert edge_checks(esquema, recibido) == [], documento
    assert topic_for(sensores["dht11_01"]) == ("vehiculo/sensor/dht11_01/registro", True)


def test_build_sensors_registra_el_dht11_junto_al_ppd42ns():
    Device.pin_factory = MockFactory()  # el PPD42NS abre su GPIO al construirse
    sensores = main.build_sensors()
    try:
        (dht11,) = [s for s in sensores if isinstance(s, DHT11Sensor)]
        assert dht11.sensor_id == config.DHT11_SENSOR_ID
        assert dht11.gpio_bcm == config.DHT11_GPIO_BCM == PIN
        assert dht11.sample_window_seconds == config.DHT11_PERIOD_SECONDS == PERIODO
        assert config.PPD42NS_SENSOR_ID in {s.sensor_id for s in sensores}
    finally:
        for sensor in sensores:
            sensor.close()
        Device.pin_factory.close()
