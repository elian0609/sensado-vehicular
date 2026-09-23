# Nodo Edge (H2) — M1 + M2 hasta la salida de KI-1

```
PPD42NS --GPIO4--> M1 (sensors/ppd42ns.py, hilo propio, ventana 30 s)
                     |  Observation (contrato interno, sin semántica)
                     v
                   M2 (semantic/annotator.py) --> JSON-LD 1.1
                     |
                     v
                   KI-1 (sinks/base.py -> outbox_ki1.jsonl; MQTT en Fase 4)
```

## Instalación en la Raspberry Pi
```bash
scp -r edge_node elian-trelles@raspberrypi.local:~/
ssh elian-trelles@raspberrypi.local
sudo apt install -y python3-gpiozero python3-lgpio
pip3 install pyld --break-system-packages      # solo para validar
```

## Ejecución
```bash
cd ~/edge_node
python3 main.py                        # sensado real, hasta Ctrl+C
python3 main.py --simulate --window 3 --max 5   # prueba sin hardware
python3 -m tools.validate_jsonld outbox_ki1.jsonl --show
```

## Sesiones de horas (arranque automático al encender la Pi)
`/etc/systemd/system/edge-node.service`:
```ini
[Unit]
Description=Nodo Edge - M1/M2
After=time-sync.target

[Service]
WorkingDirectory=/home/elian-trelles/edge_node
ExecStart=/usr/bin/python3 main.py
User=elian-trelles
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now edge-node
journalctl -u edge-node -f
```

## Parámetros críticos
Todos en `config.py`. Antes de la versión final, reemplazar `PROJECT_NS`.
