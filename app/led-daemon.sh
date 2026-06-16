#!/bin/bash
PY=/opt/fipradio/venv/bin/python3
LED=/opt/fipradio/led.py
for i in $(seq 1 40); do mpc status >/dev/null 2>&1 && break; sleep 1; done
sleep 2
$PY $LED auto || true
while true; do
  mpc idle player mixer >/dev/null 2>&1 || sleep 2
  $PY $LED auto || true
done
