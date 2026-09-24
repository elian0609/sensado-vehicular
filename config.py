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

# --- Metadatos de registro (DIV-3) ------------------------------------------
# Datos de configuración, no mediciones: se emiten una vez al iniciar el nodo.
PPD42NS_METADATA = {
    "sensor_model": "PPD42NS",
    "sensor_type": "particulate_matter",
    "calibration_params": {"voltage_divider_r1_ohm": 1000,
                           "voltage_divider_r2_ohm": 2000},
    "install_date": "2026-08-19",     # REEMPLAZAR por la fecha real de montaje
    "status": "activo",
}

OBSERVED_PROPERTIES = {
    "low_pulse_occupancy_ratio": {"unit": "ratio_0_1"},
}

PLATFORM = {
    "vehicle_id": "moto_01",
    "vehicle_type": "motocicleta",
    "route_label": None,              # se define en las pruebas de campo (Fase 6)
    "registration_date": "2026-09-24",
}

# --- Salida hacia KI-1 -------------------------------------------------------
# Hasta que la Fase 4 defina el transporte (MQTT), la salida de M2 se escribe
# en un archivo JSON Lines que actúa como bandeja de salida de KI-1.
OUTBOX_PATH = "outbox_ki1.jsonl"

assert PROJECT_NS.endswith("/") and "github.com" not in PROJECT_NS, \
    "PROJECT_NS debe ser la URL del sitio publicado y terminar en '/'"
