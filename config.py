"""
Parámetros críticos del Nodo Edge (H2).

Todo valor que la metodología declara como "parámetro crítico" vive aquí,
en un solo lugar, para que el experimento sea reproducible sin leer el código.

Los valores OPERATIVOS se pueden sobrescribir con variables de entorno EDGE_*
(ver load_settings() al final y deploy/edge-node.env.example); los valores de
este archivo son los valores por defecto documentados. Los IRIs del proyecto
(PROJECT_NS, VOCAB_NS, ID_BASE) NO son configurables: forman parte del contrato
KI-1 v2 y cambiarlos cambiaría la identidad de todas las observaciones.
"""

import os
import sys
from collections.abc import Mapping
from typing import Any

# Requisito de versión (pyproject.toml: requires-python). config se importa antes que
# cualquier otro módulo del nodo en main.py, así que el fallo es claro y temprano.
if sys.version_info < (3, 11):  # noqa: UP036 (guarda intencional para la Pi)
    raise SystemExit(
        f"edge_node requiere Python >= 3.11 (la Pi de referencia: Debian 13 trixie, Python 3.13); "
        f"se está usando {sys.version.split()[0]}"
    )

# --- Espacios de nombres (DIV-3) --------------------------------------------
# REEMPLAZAR antes de la versión final por el dominio definitivo del proyecto
# (p. ej. una URL de GitHub Pages del repositorio). Solo cambia aquí; ningún
# otro archivo necesita modificarse.
PROJECT_NS = "https://elian0609.github.io/sensado-vehicular/"
VOCAB_NS = PROJECT_NS + "vocab#"  # prefijo proy: (extensiones propias)
ID_BASE = PROJECT_NS + "id/"  # @base: resuelve los identificadores compactos

# --- Observación (DIV-2) -----------------------------------------------------
DEFAULT_FEATURE_OF_INTEREST = "ambient_air_at_device"

# Objetos de interés publicados como registro sosa:FeatureOfInterest (ADR-008).
# feature_of_interest de cada observación es una IRI que apunta a uno de ellos.
FEATURES_OF_INTEREST = {
    DEFAULT_FEATURE_OF_INTEREST: {
        "feature_kind": "aire_ambiente",
        "description": "Aire ambiente en el punto de toma del sensor, a bordo de la plataforma",
    },
}

# --- Sensor PPD42NS (H1 -> H2) ----------------------------------------------
PPD42NS_SENSOR_ID = "ppd42ns_01"
PPD42NS_GPIO_BCM = 4  # pin físico 7, tras divisor 1 kΩ / 2 kΩ
PPD42NS_WINDOW_SECONDS = 30.0  # mínimo recomendado por el fabricante

# --- Sensor DHT11 (Grove, H1 -> H2) ------------------------------------------
# Lo lee el driver del kernel: dtoverlay=dht11,gpiopin=23 en /boot/firmware/config.txt.
DHT11_SENSOR_ID = "dht11_01"
DHT11_GPIO_BCM = 23  # pin físico 16; alimentado a 3,3 V (pin 1), GND en el pin 14
DHT11_PERIOD_SECONDS = 30.0  # mismo periodo que el PPD42NS (hoja de datos: >= 1 s)
DHT11_IIO_DIR = "/sys/bus/iio/devices/iio:device0"  # name = dht11@17 (verificado en la Pi)

# --- Reloj de tiempo real DS1302 (tools/rtc_ds1302.py) -----------------------
# La Pi no tiene reloj propio: sin red arrancaría con la hora del último
# apagado y los result_time serían falsos. El DS1302 (con pila CR2032) da la
# hora al arrancar. Interfaz de 3 hilos, alimentado a 3,3 V (pin 17).
RTC_DS1302_GPIO_CLK = 17  # pin físico 11
RTC_DS1302_GPIO_DAT = 27  # pin físico 13
RTC_DS1302_GPIO_RST = 22  # pin físico 15 (CE)

# --- Corrección de la hora con el gateway (core/clock.py) --------------------
# Sin internet, la app publica la hora del teléfono en KI-1 y el nodo corrige
# su reloj (y el RTC) si se desvió. Con NTP sincronizado no se aplica.
CLOCK_SYNC_MIN_OFFSET_S = 1.0  # desfase por debajo del cual no se toca
CLOCK_SYNC_MAX_BACKWARD_S = 20  # retroceso máximo (más repetiría result_time)
CLOCK_GATEWAY_VALID_S = 6 * 3600  # una corrección del gateway vale 6 h
CLOCK_MIN_VALID_YEAR = 2026

# --- Metadatos de registro (DIV-3) ------------------------------------------
# Datos de configuración, no mediciones: se emiten una vez al iniciar el nodo.
PPD42NS_METADATA = {
    "sensor_model": "PPD42NS",
    "sensor_type": "particulate_matter",
    "calibration_params": {"voltage_divider_r1_ohm": 1000, "voltage_divider_r2_ohm": 2000},
    "install_date": "2026-10-05",  # montaje definitivo: divisor 1 kΩ/2 kΩ, GND común
    "status": "activo",
}

DHT11_METADATA = {
    "sensor_model": "DHT11",
    "sensor_type": "temperature_humidity",
    "install_date": "2026-10-27",  # cableado a GPIO23 / 3,3 V
    "status": "activo",
}

# Sensores publicados como registro sosa:Sensor (semantic/registry.py): sensor_id -> metadatos.
# Un sensor nuevo añade aquí su entrada, igual que sus propiedades en OBSERVED_PROPERTIES.
SENSOR_METADATA = {
    PPD42NS_SENSOR_ID: PPD42NS_METADATA,
    DHT11_SENSOR_ID: DHT11_METADATA,
}

OBSERVED_PROPERTIES = {
    "low_pulse_occupancy_ratio": {"unit": "ratio_0_1"},
    "air_temperature": {"unit": "degree_celsius"},
    "relative_humidity": {"unit": "percent_rh"},
}

PLATFORM = {
    "vehicle_id": "moto_01",
    "vehicle_type": "motocicleta",
    # Fase 6: poner la etiqueta de la ruta antes de cada sesión de campo
    # (p. ej. "ruta_centro_01"). Con None no se publica en el registro.
    "route_label": None,
    "registration_date": "2026-09-24",
}

# --- KI-1: transporte MQTT (Fase 4) -----------------------------------------
# El broker (Mosquitto) se ejecuta en el propio nodo edge, por lo que el nombre
# por defecto es "localhost". Se configura por nombre de dominio, nunca por IP:
# si el broker se trasladara a otro equipo, basta con cambiar este nombre
# (p. ej. "otro-equipo.local" vía mDNS) o pasar --broker al ejecutar.
# El hostname de la Pi debe ser "raspberrypi": el gateway (app móvil) localiza
# el broker como raspberrypi.local.
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_CLIENT_ID = "nodo_edge_moto_01"  # único por nodo edge
MQTT_QOS = 1  # al menos una vez: sin pérdida de observaciones
MQTT_KEEPALIVE = 60  # segundos
MQTT_TOPIC_ROOT = "vehiculo"  # raíz de la jerarquía de tópicos (sinks/topics.py)
MQTT_USERNAME = None  # None: broker sin autenticación (WLAN privada)
MQTT_PASSWORD = None

# Bandeja en archivo JSON Lines: se escribe siempre, en paralelo con MQTT, como
# respaldo y referencia de lo publicado (Fase 6: comparación con lo recibido
# por el gateway). Con --sink file es la única salida (pruebas sin broker).
OUTBOX_PATH = "outbox_ki1.jsonl"

# Observaciones que fallaron en M2 (anotación, serialización, tópico o envío):
# la observación cruda y el motivo, en JSON Lines con fsync (core/pipeline.py).
ERRORS_PATH = "outbox_ki1_errors.jsonl"

# --- Operación ---------------------------------------------------------------
LOG_LEVEL = "INFO"
# Al recibir SIGTERM, tiempo máximo para procesar las observaciones que quedan
# en la cola interna antes de cerrar los sinks.
SHUTDOWN_DRAIN_SECONDS = 10.0

assert PROJECT_NS.endswith("/") and "github.com" not in PROJECT_NS, (
    "PROJECT_NS debe ser la URL del sitio publicado y terminar en '/'"
)


# --- Configuración por entorno (EDGE_*) ---------------------------------------


class ConfigError(ValueError):
    """Variable de entorno EDGE_* con un valor no válido."""


_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def _texto(variable: str, valor: str) -> str:
    if not valor.strip():
        raise ConfigError(f"{variable} no puede estar vacía")
    return valor


def _host(variable: str, valor: str) -> str:
    if not valor or any(c.isspace() for c in valor):
        raise ConfigError(f"{variable} debe ser un nombre de host sin espacios: {valor!r}")
    return valor


def _numero(tipo, minimo, maximo):
    def convertir(variable: str, valor: str):
        try:
            numero = tipo(valor)
        except ValueError:
            raise ConfigError(f"{variable} debe ser un {tipo.__name__}: {valor!r}") from None
        if not minimo <= numero <= maximo:
            raise ConfigError(f"{variable} debe estar entre {minimo} y {maximo}: {valor!r}")
        return numero

    return convertir


def _ventana(variable: str, valor: str) -> float:
    numero = _numero(float, 0.0, 600.0)(variable, valor)
    if numero <= 0:
        raise ConfigError(f"{variable} debe ser mayor que 0: {valor!r}")
    return numero


def _client_id(variable: str, valor: str) -> str:
    # MQTT 3.1.1 garantiza client_id de 1 a 23 caracteres en cualquier broker.
    if not 1 <= len(valor) <= 23:
        raise ConfigError(f"{variable} debe tener entre 1 y 23 caracteres: {valor!r}")
    return valor


def _nivel(variable: str, valor: str) -> str:
    nivel = valor.strip().upper()
    if nivel not in _LOG_LEVELS:
        raise ConfigError(f"{variable} debe ser uno de {', '.join(_LOG_LEVELS)}: {valor!r}")
    return nivel


# variable de entorno -> (atributo de config, conversor y validador)
ENV_VARIABLES = {
    "EDGE_MQTT_HOST": ("MQTT_BROKER_HOST", _host),
    "EDGE_MQTT_PORT": ("MQTT_BROKER_PORT", _numero(int, 1, 65535)),
    "EDGE_MQTT_CLIENT_ID": ("MQTT_CLIENT_ID", _client_id),
    "EDGE_OUTBOX_PATH": ("OUTBOX_PATH", _texto),
    "EDGE_ERRORS_PATH": ("ERRORS_PATH", _texto),
    "EDGE_WINDOW_SECONDS": ("PPD42NS_WINDOW_SECONDS", _ventana),
    "EDGE_LOG_LEVEL": ("LOG_LEVEL", _nivel),
    "EDGE_SHUTDOWN_DRAIN_SECONDS": ("SHUTDOWN_DRAIN_SECONDS", _numero(float, 0.0, 120.0)),
}

_DEFAULTS = {atributo: globals()[atributo] for atributo, _ in ENV_VARIABLES.values()}


def load_settings(environ: Mapping[str, str]) -> dict[str, Any]:
    """Valores operativos: los de este archivo, sobrescritos por las EDGE_* presentes.

    Valida tipos y rangos y lanza ConfigError con el nombre de la variable si alguna
    no es válida. No modifica el módulo (apply_environment() lo hace).
    """
    ajustes = dict(_DEFAULTS)
    for variable, (atributo, convertir) in ENV_VARIABLES.items():
        if variable in environ:
            ajustes[atributo] = convertir(variable, environ[variable])
    if os.path.abspath(ajustes["OUTBOX_PATH"]) == os.path.abspath(ajustes["ERRORS_PATH"]):
        raise ConfigError("EDGE_ERRORS_PATH no puede ser el mismo archivo que EDGE_OUTBOX_PATH")
    return ajustes


def apply_environment(environ: Mapping[str, str] = os.environ) -> dict[str, Any]:
    """Aplica load_settings() a este módulo. main.py lo llama al arrancar."""
    ajustes = load_settings(environ)
    globals().update(ajustes)
    return ajustes
