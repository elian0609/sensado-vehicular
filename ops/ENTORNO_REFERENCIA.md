# Entorno de referencia del nodo edge (Raspberry Pi)

Plantilla para registrar, **en la Pi**, el entorno exacto con el que se capturan las trazas y se
ejecuta el nivel edge del experimento (`MCS_BACKEND/docs/arquitectura/PROTOCOLO_EXPERIMENTAL.md`, §4).
Completar los campos vacíos copiando la salida de cada comando. Volver a completarla si cambia el SO,
una dependencia o el hardware.

- **Fecha de registro:** 2026-10-17
- **Registrado por:** Claude Code por SSH, a petición del autor (Elian Trelles)
- **Commit de edge_node** (`git rev-parse HEAD`): `8fa415efdb02ec23bdf6fec97b495c518b421a2d`

## Hardware

| Campo | Comando | Valor |
|---|---|---|
| Modelo | `cat /proc/device-tree/model; echo` || Raspberry Pi 3 Model B Rev 1.2 |
| Memoria | `free -h \| head -2` || 905 MiB |
| Tarjeta SD (capacidad) | `lsblk -d -o NAME,SIZE,MODEL` || `mmcblk0` 59,6 G |
| Alimentación sin estrangulamiento | `vcgencmd get_throttled` (esperado `throttled=0x0`) || `throttled=0x0` |
| Temperatura en reposo | `vcgencmd measure_temp` || 42,9 °C |

## Sistema operativo

| Campo | Comando | Valor |
|---|---|---|
| Distribución y versión | `cat /etc/os-release` || Debian GNU/Linux 13 (trixie) |
| Kernel | `uname -a` || `Linux raspberrypi 6.18.39+rpt-rpi-v8 #1 SMP PREEMPT Debian 1:6.18.39-1+rpt1 (2026-07-29) aarch64` |
| Arquitectura (armv7l = 32 bits, aarch64 = 64 bits) | `uname -m` || `aarch64` |
| Hostname (debe ser `raspberrypi`) | `hostnamectl hostname` || `raspberrypi` |
| Sincronización NTP | `timedatectl show -p NTPSynchronized --value` || `yes` |

## Python y dependencias

| Campo | Comando | Valor |
|---|---|---|
| Python | `python3 --version` || Python 3.13.5 |
| Paquetes del sistema | `dpkg -l python3-gpiozero python3-lgpio python3-paho-mqtt \| tail -3` || python3-gpiozero 2.0.1-0+rpt1+trixie; python3-lgpio 0.2.2-1~rpt1+trixie; python3-paho-mqtt 2.1.0-1 |
| Paquetes pip | `python3 -m pip freeze \| grep -iE "gpiozero\|lgpio\|paho\|pyld"` || gpiozero==2.0.1, lgpio==0.2.2.0, paho-mqtt==2.1.0, PyLD==3.3.0, rpi-lgpio==0.6 |
| Coinciden con `requirements.txt` (sí/no y diferencias) | comparar con `requirements.txt` || Sí (gpiozero 2.0.1, lgpio 0.2.2.0, paho-mqtt 2.1.0) |

## Broker y red

| Campo | Comando | Valor |
|---|---|---|
| Mosquitto | `mosquitto -h \| head -1` || mosquitto version 2.0.21 (`/usr/sbin/mosquitto`; no está en el PATH del usuario) |
| Configuración de KI-1 instalada | `diff deploy/mosquitto/ki1.conf /etc/mosquitto/conf.d/ki1.conf && echo igual` || igual |
| Interfaz WLAN | `ip -br addr show wlan0` || `wlan0 UP 192.168.1.100/24` |
| Red a la que está conectada | `iwgetid -r` || `COCOLON` (señal 86). `iwgetid` no está instalado: `nmcli -t -f ACTIVE,SSID,SIGNAL dev wifi`. Perfiles: `COCOLON` (prioridad 0) y `hotspot-movil` (SSID `nodo-moto01`, prioridad 10) |
| Potencia y calidad de señal | `iwconfig wlan0 \| grep -E "Quality\|Tx-Power"` || Señal 86 % (nmcli); `iwconfig` no está instalado |
| Anuncio DNS-SD del broker | `avahi-browse -rtp _mqtt._tcp \| grep "^="` || `avahi-browse` no está instalado en la Pi; desde la PC: `Broker KI-1 en raspberrypi` `_mqtt._tcp` 192.168.1.100:1883 `topic_root=vehiculo` |

## Servicio

| Campo | Comando | Valor |
|---|---|---|
| Servicio activo | `systemctl is-active edge-node` || `active` |
| Unidad efectiva (usuario y ruta) | `systemctl cat edge-node \| grep -E "User=\|WorkingDirectory=\|EnvironmentFile="` || `User=elian-trelles`, `WorkingDirectory=/home/elian-trelles/sensado-vehicular`, `EnvironmentFile=-/etc/edge-node.env` |
| Variables EDGE_* aplicadas | `grep -v "^#" /etc/edge-node.env \| grep .` (vacío = valores por defecto) || vacío (valores por defecto) |
| RTC DS1302 frente al sistema | `python3 -m tools.rtc_ds1302 leer` || RTC `2026-10-18T01:24:45+00:00`; desfase RTC − sistema: +170 ms |
