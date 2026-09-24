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

# --- Salida hacia KI-1 -------------------------------------------------------
# Hasta que la Fase 4 defina el transporte (MQTT), la salida de M2 se escribe
# en un archivo JSON Lines que actúa como bandeja de salida de KI-1.
OUTBOX_PATH = "outbox_ki1.jsonl"
