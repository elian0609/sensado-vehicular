# Entorno de referencia del nodo edge (Raspberry Pi)

Plantilla para registrar, **en la Pi**, el entorno exacto con el que se capturan las trazas y se
ejecuta el nivel edge del experimento (`MCS_BACKEND/docs/arquitectura/PROTOCOLO_EXPERIMENTAL.md`, §4).
Completar los campos vacíos copiando la salida de cada comando. Volver a completarla si cambia el SO,
una dependencia o el hardware.

- **Fecha de registro:**
- **Registrado por:**
- **Commit de edge_node** (`git rev-parse HEAD`):

## Hardware

| Campo | Comando | Valor |
|---|---|---|
| Modelo | `cat /proc/device-tree/model; echo` | |
| Memoria | `free -h \| head -2` | |
| Tarjeta SD (capacidad) | `lsblk -d -o NAME,SIZE,MODEL` | |
| Alimentación sin estrangulamiento | `vcgencmd get_throttled` (esperado `throttled=0x0`) | |
| Temperatura en reposo | `vcgencmd measure_temp` | |

## Sistema operativo

| Campo | Comando | Valor |
|---|---|---|
| Distribución y versión | `cat /etc/os-release` | |
| Kernel | `uname -a` | |
| Arquitectura (armv7l = 32 bits, aarch64 = 64 bits) | `uname -m` | |
| Hostname (debe ser `raspberrypi`) | `hostnamectl hostname` | |
| Sincronización NTP | `timedatectl show -p NTPSynchronized --value` | |

## Python y dependencias

| Campo | Comando | Valor |
|---|---|---|
| Python | `python3 --version` | |
| Paquetes del sistema | `dpkg -l python3-gpiozero python3-lgpio python3-paho-mqtt \| tail -3` | |
| Paquetes pip | `python3 -m pip freeze \| grep -iE "gpiozero\|lgpio\|paho\|pyld"` | |
| Coinciden con `requirements.txt` (sí/no y diferencias) | comparar con `requirements.txt` | |

## Broker y red

| Campo | Comando | Valor |
|---|---|---|
| Mosquitto | `mosquitto -h \| head -1` | |
| Configuración de KI-1 instalada | `diff deploy/mosquitto/ki1.conf /etc/mosquitto/conf.d/ki1.conf && echo igual` | |
| Interfaz WLAN | `ip -br addr show wlan0` | |
| Red a la que está conectada | `iwgetid -r` | |
| Potencia y calidad de señal | `iwconfig wlan0 \| grep -E "Quality\|Tx-Power"` | |
| Anuncio DNS-SD del broker | `avahi-browse -rtp _mqtt._tcp \| grep "^="` | |

## Servicio

| Campo | Comando | Valor |
|---|---|---|
| Servicio activo | `systemctl is-active edge-node` | |
| Unidad efectiva (usuario y ruta) | `systemctl cat edge-node \| grep -E "User=\|WorkingDirectory=\|EnvironmentFile="` | |
| Variables EDGE_* aplicadas | `grep -v "^#" /etc/edge-node.env \| grep .` (vacío = valores por defecto) | |
| RTC DS1302 frente al sistema | `python3 -m tools.rtc_ds1302 leer` | |
