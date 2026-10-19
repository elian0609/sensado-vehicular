# Fixtures de la captura piloto (2026-10-19)

Para las pruebas del replay (Iteración 5): fidelidad del modo semántico frente a lo que emitió el
edge en campo.

| Archivo | Origen | SHA-256 |
|---|---|---|
| `outbox_ki1_piloto.jsonl` | `outbox_ki1.jsonl` de la Pi, 54 observaciones de 16:36–17:03 UTC, sin cambios (MCS_BACKEND `experiment/traces/piloto/outbox_ki1_piloto.jsonl`) | `83ab8e4d…8b338` |
| `traza_base_sin_posicion.jsonl` | MCS_BACKEND `experiment/traces/piloto/traza_base.jsonl` (SHA-256 `1502e045…bd31d`) **sin** `latitude`, `longitude` ni `position_source`, que añade la app y no intervienen en el nivel edge. Se quitan porque este repositorio es público y la traza contiene la ubicación del autor | `9fb7b6b1…06ba3` |

No se editan a mano. Para regenerarlas, quitar esas tres claves de cada línea de la traza base y
volver a serializar en JSON canónico (claves ordenadas, compacto, UTF-8).
