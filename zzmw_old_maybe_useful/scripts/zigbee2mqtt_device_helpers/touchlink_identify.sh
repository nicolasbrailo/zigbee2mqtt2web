#!/usr/bin/bash
set -euo pipefail
ADDR="$1"
CH="$2"
mosquitto_pub -t zigbee2mqtt/bridge/request/touchlink/identify -m '{"ieee_address": "'$ADDR'", "channel": '$CH' }'
