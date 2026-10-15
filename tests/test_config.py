"""Configuración operativa por variables de entorno EDGE_* (config.load_settings)."""

import pytest

import config
from config import ConfigError, load_settings

DEFECTOS = {
    "MQTT_BROKER_HOST": "localhost",
    "MQTT_BROKER_PORT": 1883,
    "MQTT_CLIENT_ID": "nodo_edge_moto_01",
    "OUTBOX_PATH": "outbox_ki1.jsonl",
    "ERRORS_PATH": "outbox_ki1_errors.jsonl",
    "PPD42NS_WINDOW_SECONDS": 30.0,
    "LOG_LEVEL": "INFO",
    "SHUTDOWN_DRAIN_SECONDS": 10.0,
}


def test_sin_variables_se_usan_los_valores_documentados():
    assert load_settings({}) == DEFECTOS


def test_las_variables_edge_sobrescriben_los_valores():
    ajustes = load_settings(
        {
            "EDGE_MQTT_HOST": "broker.local",
            "EDGE_MQTT_PORT": "1884",
            "EDGE_MQTT_CLIENT_ID": "nodo_edge_moto_02",
            "EDGE_OUTBOX_PATH": "/var/lib/edge/outbox.jsonl",
            "EDGE_ERRORS_PATH": "/var/lib/edge/errores.jsonl",
            "EDGE_WINDOW_SECONDS": "15",
            "EDGE_LOG_LEVEL": "debug",
            "EDGE_SHUTDOWN_DRAIN_SECONDS": "3.5",
        }
    )
    assert ajustes == {
        "MQTT_BROKER_HOST": "broker.local",
        "MQTT_BROKER_PORT": 1884,
        "MQTT_CLIENT_ID": "nodo_edge_moto_02",
        "OUTBOX_PATH": "/var/lib/edge/outbox.jsonl",
        "ERRORS_PATH": "/var/lib/edge/errores.jsonl",
        "PPD42NS_WINDOW_SECONDS": 15.0,
        "LOG_LEVEL": "DEBUG",
        "SHUTDOWN_DRAIN_SECONDS": 3.5,
    }


def test_variables_ajenas_se_ignoran():
    assert load_settings({"PATH": "/usr/bin", "EDGE_DESCONOCIDA": "x"}) == DEFECTOS


@pytest.mark.parametrize(
    ("variable", "valor"),
    [
        ("EDGE_MQTT_PORT", "abc"),
        ("EDGE_MQTT_PORT", "0"),
        ("EDGE_MQTT_PORT", "70000"),
        ("EDGE_MQTT_HOST", ""),
        ("EDGE_MQTT_HOST", "con espacio"),
        ("EDGE_MQTT_CLIENT_ID", ""),
        ("EDGE_MQTT_CLIENT_ID", "x" * 24),
        ("EDGE_WINDOW_SECONDS", "0"),
        ("EDGE_WINDOW_SECONDS", "-5"),
        ("EDGE_WINDOW_SECONDS", "601"),
        ("EDGE_WINDOW_SECONDS", "treinta"),
        ("EDGE_LOG_LEVEL", "VERBOSE"),
        ("EDGE_SHUTDOWN_DRAIN_SECONDS", "-1"),
        ("EDGE_SHUTDOWN_DRAIN_SECONDS", "121"),
        ("EDGE_OUTBOX_PATH", ""),
        ("EDGE_ERRORS_PATH", " "),
    ],
)
def test_valores_invalidos_fallan_con_un_mensaje_que_nombra_la_variable(variable, valor):
    with pytest.raises(ConfigError, match=variable):
        load_settings({variable: valor})


def test_outbox_y_errores_no_pueden_ser_el_mismo_archivo():
    with pytest.raises(ConfigError, match="EDGE_ERRORS_PATH"):
        load_settings({"EDGE_OUTBOX_PATH": "a.jsonl", "EDGE_ERRORS_PATH": "a.jsonl"})


def test_los_iris_del_proyecto_no_son_configurables():
    ajustes = load_settings({"EDGE_ID_BASE": "https://otro/", "EDGE_PROJECT_NS": "https://otro/"})
    assert "ID_BASE" not in ajustes and "PROJECT_NS" not in ajustes
    assert config.ID_BASE == "https://elian0609.github.io/sensado-vehicular/id/"
