#!/usr/bin/bash
set -euo pipefail
echo "Scanning..."
mosquitto_pub -t 'zigbee2mqtt/bridge/request/touchlink/scan' -m ''
journalctl -f -u zigbee2mqtt.service | grep touchlink/scan

