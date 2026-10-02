# Nota para el gateway (app MCP_APP): ajustes en KI-1

El nodo edge ya publica en KI-1 según el contrato de la Fase 4 (ver README).
La app es compatible en tópicos, QoS, `client_id` fijo, formato de carga útil
(lee los términos compactos del JSON-LD e ignora `@context`) y localización del
broker por nombre (`raspberrypi.local`). Quedan dos ajustes del lado de la app.

## 1. Sesión persistente: `clean_session = false`

**Dónde:** `lib/features/edge_mqtt/data/mqtt_edge_receiver.dart:96-99`

```dart
final connMess = MqttConnectMessage()
    .withClientIdentifier(clientId)
    .startClean()                       // <- clean_session = true
    .withWillQos(MqttQos.atLeastOnce);
```

**Cambio:** quitar `.startClean()` (en `mqtt_client` el valor por defecto de
la bandera es `cleanStart = false`). El `client_id` fijo
(`flutter_mobile_gateway_h3`) ya está.

**Por qué:** con `clean_session = true` el broker no guarda la sesión del
teléfono. Todo lo que el nodo publique mientras la app está desconectada
(hotspot caído, app cerrada por el sistema, reinicio) se descarta. Solo se
recuperan los registros, porque llevan `retain`.

**Evidencia** (Mosquitto 2.0.18 con `deploy/mosquitto/ki1.conf`, 2026-09-30):
con el gateway desconectado, el nodo publicó 3 observaciones y luego el
gateway se reconectó.

| Gateway | `session_present` | Observaciones recibidas |
|---|---|---|
| Como la app actual (`clean_session=true`) | False | **0 de 3** |
| Según contrato (`clean_session=false`) | True | **3 de 3** |

El broker de la Pi guarda hasta 3000 mensajes por sesión (unas 25 h a 30 s por
observación) y persiste en disco cada 60 s.

**A revisar al hacer el cambio:** con sesión persistente, el broker entrega lo
acumulado justo después del CONNACK. En `_onConnected` la suscripción a
`_client!.updates` se crea después de `subscribe`. Conviene comprobar que los
primeros mensajes acumulados no se pierdan antes de que exista el listener
(por ejemplo, desconectar la app, dejar que el nodo publique y verificar en
SQLite que llegan todos).

## 2. Deduplicación de observaciones por la clave del DIV-2

QoS 1 es "al menos una vez": una observación puede llegar repetida (reenvío tras
una reconexión con el PUBACK perdido). Hoy `telemetry_local_datasource.dart`
inserta sin comprobar, así que un duplicado se convierte en otra fila y se
sincroniza dos veces hacia KI-2.

**Clave:** `(sensor_id, observed_property, result_time)`, la clave compuesta
de la Observación en el DIV-2. `result_time` se usa tal cual llega del nodo
(ISO 8601 UTC con `Z`, resolución de segundos), sin reformatear.

**Cambio propuesto** (`database_helper.dart`, migración de la versión 1 a la 2):

```sql
ALTER TABLE telemetry_observations ADD COLUMN observed_property TEXT;
-- rellenar desde json_payload para las filas existentes, eliminar los duplicados
-- ya presentes y luego:
CREATE UNIQUE INDEX ux_telemetry_obs_key
  ON telemetry_observations (sensor_id, observed_property, result_time);
```

- `TelemetryObservationEntity.toMap()` debe incluir `observed_property`.
- El `insert` de `TelemetryLocalDataSource` debe usar
  `conflictAlgorithm: ConflictAlgorithm.ignore`: el duplicado se descarta y se
  conserva la fila original, con su `synced` y su `batch_id`.
- Subir `AppConstants.databaseVersion` a 2 e implementar `onUpgrade`.

Así la inserción es idempotente y el backend de KI-2 no recibe observaciones
repetidas desde el gateway.

## 3. (Menor) Registros que se re-sincronizan

Los registros llegan de nuevo en cada suscripción (llevan `retain`). El upsert
con `ConflictAlgorithm.replace` los vuelve a marcar `synced = 0`, así que se
reenvían a la nube en cada reconexión. Si interesa evitarlo, basta con no
reemplazar la fila cuando `json_payload` no cambió.
