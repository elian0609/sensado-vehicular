# Nota para el gateway (app MCP_APP): estado de KI-1

El nodo edge publica en KI-1 según el contrato de la Fase 4 (ver README). La app
es compatible en tópicos, QoS, `client_id` fijo y formato de carga útil (lee
los términos compactos del JSON-LD e ignora `@context`).

Las pruebas reales con el teléfono (Infinix X6852, Android 15) y la Raspberry
Pi mostraron varios problemas en la app. Todos están corregidos en la rama
**`fix/ki1-descubrimiento-hotspot`** del repositorio MCP_APP (sección A). La
sección B recoge lo que sigue abierto.

## A. Cambios ya hechos (rama `fix/ki1-descubrimiento-hotspot`)

### A1. Localizar el broker por nombre cuando el teléfono es el hotspot

**Problema:** con el teléfono como punto de acceso (escenario de campo), la app
no resolvía `raspberrypi.local`:

```
Advertencia: No se pudo resolver raspberrypi.local via mDNS, intentando conexión directa...
Error conectando a broker MQTT: SocketException: Failed host lookup:
'raspberrypi.local' (OS Error: No address associated with hostname, errno = 7)
```

**Causa (verificada con `adb` desde el teléfono, 2026-10-02):**
- La Pi sí anuncia su nombre en la red del hotspot. Una consulta mDNS
  **unicast** a `10.70.243.150:5353` recibió de Avahi
  `raspberrypi.local → 10.70.243.150`.
- La consulta **multicast** (`224.0.0.251:5353`), que es la que usa
  `multicast_dns`, falla con `Network is unreachable`. Android no deja a las
  apps enviar multicast por la interfaz del punto de acceso (`ap0`), porque
  pertenece al anclaje de red del sistema.
- Además, `MdnsResolver` iniciaba el cliente mDNS una sola vez. Si la red
  cambiaba (por ejemplo, al activar el hotspot), seguía usando las interfaces
  antiguas.
- El resolvedor del sistema (`getaddrinfo`) no resuelve nombres `.local`.

**Cambio** (`lib/features/edge_mqtt/data/mdns_resolver.dart`):
1. **Unicast primero:** la app envía la consulta mDNS de tipo A al puerto 5353
   de cada host de las subredes /24 locales (Wi-Fi cliente o hotspot) y toma
   la primera respuesta. Tiempo de espera: 2 s
   (`AppConstants.mdnsUnicastTimeout`). Se excluyen las interfaces celulares y
   virtuales (`rmnet`, `ccmni`, `tun`…).
2. **Multicast como respaldo**, con un cliente nuevo en cada consulta para usar
   las interfaces actuales.
3. Las interfaces se leen en cada resolución, así que cambiar de red no exige
   reiniciar la app.

El broker se sigue localizando **por nombre**, sin IP fija, y no se añaden
permisos ni dependencias.

### A2. Sesión persistente: `clean_session = false`

**Cambio** (`lib/features/edge_mqtt/data/mqtt_edge_receiver.dart`):
- Se quitó `.startClean()`. En `mqtt_client` la bandera vale `false` por
  defecto. Con el `client_id` fijo (`flutter_mobile_gateway_h3`), el broker
  guarda las observaciones QoS 1 mientras la app está desconectada.
- El listener de `updates` se crea **antes** de esperar al CONNACK.
  `connect()` crea ese stream de forma síncrona, así que los mensajes
  acumulados que el broker entrega al reconectar no se pierden. Antes se
  creaba en `_onConnected`.

### A3. Servicio en primer plano declarado

**Problema:** el plugin `flutter_foreground_task` 6.5.0 no declara su servicio
y la app tampoco lo hacía. `logcat` mostraba
`Unable to start service ... K0.a ... not found`, y con la pantalla apagada
Android podía cortar MQTT y el GPS.

**Cambio:**
- `android/app/src/main/AndroidManifest.xml`: se declara
  `com.pravera.flutter_foreground_task.service.ForegroundService` con
  `foregroundServiceType="location"`, porque la pasarela enriquece con GPS y
  ese tipo no tiene límite diario de tiempo.
- `gateway_state_provider.dart`: el servicio se inicia **después** de pedir el
  permiso de ubicación, y solo si se concede. Android exige ese permiso para el
  tipo `location`; si falta, la app se cerraría.

Comprobado en el teléfono: `isForeground=true types=0x00000008` (location).

### A4. Deduplicación de observaciones por la clave del DIV-2

QoS 1 es "al menos una vez": una observación puede llegar repetida, por ejemplo
reenviada tras una reconexión con el PUBACK perdido. Con la sesión persistente
(A2) las reentregas son más probables. Antes, cada duplicado se guardaba como
otra fila y se sincronizaba dos veces hacia KI-2.

**Clave:** `(sensor_id, observed_property, result_time)`, la clave compuesta de
la Observación en el DIV-2. `result_time` se usa tal cual llega del nodo, sin
reformatear.

**Cambio:**
- `database_helper.dart`: base de datos en la **versión 2**, con la columna
  `observed_property` y el índice único `ux_telemetry_obs_key`. La migración
  desde la versión 1 rellena la columna desde `json_payload`, elimina los
  duplicados que ya existían (conserva la fila más antigua, con su `synced` y su
  `batch_id`) y crea el índice.
- `telemetry_local_datasource.dart`: inserción con
  `ConflictAlgorithm.ignore`. Devuelve **0** si la observación ya existía (se
  comprueba con `SELECT changes()` dentro de la transacción).
- `mqtt_edge_receiver.dart`: un duplicado se registra en la consola
  (`Observación duplicada descartada ...`) y no se vuelve a mostrar.

### A5. La app arranca en modo real

`GatewayState.isMockMode` pasa a ser `false` por defecto. Antes, la app
arrancaba con el simulador, que guarda observaciones falsas en la misma SQLite
(una cada 10 s), y había que desactivarlo a mano en cada apertura. El simulador
sigue disponible desde DevTools para probar sin la Raspberry Pi.

### A6. Reconexión que vuelve a resolver el nombre

La reconexión automática de `mqtt_client` reutilizaba la IP ya resuelta. Si el
hotspot se reiniciaba con otra subred, la app no se recuperaba hasta pulsar
**Reconectar**. Ahora:
- `autoReconnect = false`, y el receptor gestiona la reconexión: tras perder el
  broker, reintenta a los 2, 5, 10 y luego cada 30 s
  (`AppConstants.mqttReconnectDelays`), **resolviendo `raspberrypi.local` en
  cada intento**.
- `disconnectOnNoResponsePeriod = 30 s`: si el broker deja de responder a los
  PING (por ejemplo, porque se cayó el hotspot), la conexión se da por perdida y
  empieza la reconexión.
- Una desconexión manual o el cierre del receptor detienen los reintentos.

### A7. Etiqueta del valor principal

"LOW PULSE RATIO (PM₂.₅)" pasa a **"LPO · PARTÍCULAS > 1 µm"**. El canal P1 del
PPD42NS detecta partículas de más de 1 µm, y el LPO es una fracción de tiempo,
no una concentración de PM2.5. La notificación del servicio también cambió
("Sensado activo", "LPO: ...").

### A8. Los registros ya no se re-sincronizan en cada reconexión

Los registros llegan de nuevo en cada suscripción (llevan `retain`). Antes, el
upsert con `ConflictAlgorithm.replace` los volvía a marcar `synced = 0` y se
reenviaban a la nube cada vez. Ahora `metadata_local_datasource.dart` solo
reemplaza la fila si el `json_payload` cambió.

### A9. Geolocalización por `result_time` (rama `feat/geolocalizacion-result-time`)

**Problema:** la app asignaba a cada observación la posición del teléfono en el
momento de **recibirla**. Tras una desconexión de KI-1, el broker entrega en
ráfaga las observaciones acumuladas, y todas quedaban en el punto de
reconexión: con la moto a 30 km/h, 5 min sin conexión son 10 observaciones
hasta 2,5 km fuera de su lugar.

**Por qué en H3 (M3):** es el único nodo con GPS, y el enriquecimiento espacial
ya es responsabilidad de M3. Hacerlo en H4 obligaría a subir aparte la
trayectoria y dejaría las observaciones sin posición hasta tener internet.

**Cambio:**
- `location/domain/position_history.dart` (nuevo): trayectoria GPS reciente
  (26 h, cubre la cola del broker). Para un instante t interpola entre las dos
  posiciones que lo rodean (si distan ≤ 60 s), o usa la más cercana dentro de
  30 s; si no hay ninguna, no asigna posición.
- `geolocator_location_service.dart`: una posición **cada 5 s aunque el teléfono
  esté quieto** (antes solo al moverse 1 m), para que un hueco en la trayectoria
  signifique "sin señal GPS" y no "parado". Cada posición se añade al historial.
- `mqtt_edge_receiver.dart`: busca la posición en la trayectoria para el
  `result_time`. Solo una observación medida hace menos de 30 s y sin
  trayectoria todavía usa la posición actual. En otro caso se guarda **sin
  coordenadas** antes que con unas falsas.
- Cada observación lleva `position_source`: `trayectoria_interpolada`,
  `trayectoria_cercana`, `actual` o `no_disponible`.

**Requisito:** el reloj del nodo debe ser correcto, porque se compara el
`result_time` (hora del nodo) con la hora GPS. Lo garantiza el RTC DS1302 del
nodo edge.

**Limitación:** la trayectoria está en memoria. Si Android cerrara la app
durante una desconexión, las observaciones acumuladas quedarían sin posición
(`no_disponible`), nunca con una posición errónea. El servicio en primer plano
(A3) reduce ese riesgo.

### A10. La app publica la hora del teléfono (rama `feat/hora-gateway-ki1`)

**Por qué:** el RTC DS1302 del nodo deriva ~1-2 s por día, y la
geolocalización por `result_time` (A9) compara la hora del nodo con la del GPS:
1 s de desfase ≈ 8 m a 30 km/h. Sin internet en campo, el nodo no puede
corregirse por NTP.

**Cambio:**
- `mqtt_edge_receiver.dart`: al conectarse, y luego cada 10 min
  (`AppConstants.gatewayTimePublishInterval`), publica en
  **`vehiculo/gateway/hora`** (QoS 0, sin retain):
  `{"utc": "<hora UTC del teléfono>", "fuente": "telefono"}`.
- La app ignora ese tópico al recibir (le llega por su suscripción a
  `vehiculo/#`).
- Es el **primer mensaje de la app hacia el nodo**: KI-1 pasa a ser
  bidireccional en este único tópico.

**En el nodo** (`core/clock.py`): si no tiene NTP y el desfase supera 1 s,
corrige su reloj y el RTC (nunca retrocede más de 20 s). Cada observación
indica en `raw.clock_source` si la hora venía de `ntp`, `gateway` o `rtc`.

### Pruebas

- `flutter analyze`: sin problemas.
- `flutter test`: **17 / 17**. Incluye:
  - `test/mdns_resolver_test.dart`: 4 pruebas de la consulta y de la respuesta
    DNS, una con la respuesta **real** de Avahi capturada en el hotspot;
  - `test/database_dedup_test.dart`: 4 pruebas con el esquema real
    (duplicado descartado, duplicado que conserva su `synced`, migración v1 → v2
    y registros sin cambios que no vuelven a quedar pendientes).
- Las pruebas que usan SQLite necesitan la librería de escritorio
  `libsqlite3.so` (paquete `libsqlite3-dev`). Sin instalarla, basta con
  apuntarla con `LD_LIBRARY_PATH` a un enlace a `libsqlite3.so.0`.
- En el teléfono: la app migró su base de datos a la versión 2 sin errores,
  arrancó directamente en `KI₁: MQTT` y mostró datos reales del sensor.

### Evidencia en campo simulado (2026-10-05)

Condiciones: teléfono **solo como hotspot**, sin Wi-Fi cliente y sin datos
móviles; Pi con el PPD42NS real; observaciones cada 30 s.

| Verificación | Resultado |
|---|---|
| Resolución del nombre | `raspberrypi.local -> 10.70.243.150` en menos de 1 s |
| Publicadas por el nodo (outbox) frente a guardadas en SQLite, 10:54–11:02 | **16 / 16**, sin pérdidas ni duplicados |
| App cerrada 90 s (11:00:00–11:01:30) | Las 3 observaciones publicadas en ese intervalo llegaron al reconectar |
| GPS | Lat/Lon añadidos a cada observación |
| KI-2 sin internet | Observaciones retenidas en SQLite (offline-first) |

Antes del cambio A2, en el mismo escenario de desconexión se recibían
**0 de 3** observaciones (prueba con Mosquitto local, 2026-09-30).

## B. Pendiente

### B1. Calidad de cada observación (`raw.quality_flag`)

El nodo edge marca ahora cada observación en `raw.quality_flag`:
- `ok`: medición válida.
- `stuck_low`: la señal estuvo en bajo toda la ventana sin ningún pulso (sensor
  desconectado o cable suelto). El LPO (≈ 1.0) **no es válido**.

La app ya conserva `raw` completo en SQLite y lo envía a KI-2. Queda decidir si
la app debe **mostrar un aviso** cuando llega `stuck_low`, en lugar de presentar
1.0 como si fuera una medición, y si el backend debe excluir esas observaciones.

### ~~B2. Sincronización de la hora del nodo~~ (resuelto en el nodo edge)

Resuelto con un RTC DS1302 en la Raspberry Pi (`tools/rtc_ds1302.py` y los
servicios `rtc-ds1302*`). Prueba del 2026-10-06: la Pi arrancó sin internet
tras 10 min apagada y el RTC corrigió la hora (+13 min 53 s) antes de que
empezara la adquisición. La app no necesita cambios por esto.

### B3. (Propuesta) Media de 2 minutos en la pantalla principal

Con poco polvo en el aire, el LPO de una ventana de 30 s varía mucho por azar
(de 4 a 35 pulsos entre ventanas seguidas). Una media de las últimas 4
observaciones junto al último valor daría una lectura más estable.
