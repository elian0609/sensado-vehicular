"""
Parámetros críticos del Nodo Edge (H2).

Todo valor que la metodología declara como "parámetro crítico" vive aquí,
en un solo lugar, para que el experimento sea reproducible sin leer el código.
"""

# --- Espacios de nombres (DIV-3) --------------------------------------------
# REEMPLAZAR antes de la versión final por el dominio definitivo del proyecto
# (p. ej. una URL de GitHub Pages del repositorio). Solo cambia aquí; ningún
# otro archivo necesita modificarse.
PROJECT_NS = "https://elian0609.github.io/sensado-vehicular/"
VOCAB_NS = PROJECT_NS + "vocab#"     # prefijo proy: (extensiones propias)
ID_BASE = PROJECT_NS + "id/"          # @base: resuelve los identificadores compactos

# --- Observación (DIV-2) -----------------------------------------------------
DEFAULT_FEATURE_OF_INTEREST = "ambient_air_at_device"

# --- Sensor PPD42NS (H1 -> H2) ----------------------------------------------
PPD42NS_SENSOR_ID = "ppd42ns_01"
PPD42NS_GPIO_BCM = 4                  # pin físico 7, tras divisor 1 kΩ / 2 kΩ
PPD42NS_WINDOW_SECONDS = 30.0         # mínimo recomendado por el fabricante

# --- Reloj de tiempo real DS1302 (tools/rtc_ds1302.py) -----------------------
# La Pi no tiene reloj propio: sin red arrancaría con la hora del último
# apagado y los result_time serían falsos. El DS1302 (con pila CR2032) da la
# hora al arrancar. Interfaz de 3 hilos, alimentado a 3,3 V (pin 17).
RTC_DS1302_GPIO_CLK = 17              # pin físico 11
RTC_DS1302_GPIO_DAT = 27              # pin físico 13
RTC_DS1302_GPIO_RST = 22              # pin físico 15 (CE)

# --- Metadatos de registro (DIV-3) ------------------------------------------
# Datos de configuración, no mediciones: se emiten una vez al iniciar el nodo.
PPD42NS_METADATA = {
    "sensor_model": "PPD42NS",
    "sensor_type": "particulate_matter",
    "calibration_params": {"voltage_divider_r1_ohm": 1000,
                           "voltage_divider_r2_ohm": 2000},
    "install_date": "2026-10-05",     # montaje definitivo: divisor 1 kΩ/2 kΩ, GND común
    "status": "activo",
}

OBSERVED_PROPERTIES = {
    "low_pulse_occupancy_ratio": {"unit": "ratio_0_1"},
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
MQTT_QOS = 1                          # al menos una vez: sin pérdida de observaciones
MQTT_KEEPALIVE = 60                   # segundos
MQTT_TOPIC_ROOT = "vehiculo"          # raíz de la jerarquía de tópicos (sinks/topics.py)
MQTT_USERNAME = None                  # None: broker sin autenticación (WLAN privada)
MQTT_PASSWORD = None

# Bandeja en archivo JSON Lines: se escribe siempre, en paralelo con MQTT, como
# respaldo y referencia de lo publicado (Fase 6: comparación con lo recibido
# por el gateway). Con --sink file es la única salida (pruebas sin broker).
OUTBOX_PATH = "outbox_ki1.jsonl"

assert PROJECT_NS.endswith("/") and "github.com" not in PROJECT_NS, \
    "PROJECT_NS debe ser la URL del sitio publicado y terminar en '/'"
