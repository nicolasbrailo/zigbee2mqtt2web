#!/usr/bin/bash
set -euo pipefail
echo "This will factyr reset a device in range, identified with touchlink_identify. If sure, exec:"
echo mosquitto_pub -t zigbee2mqtt/bridge/request/touchlink/factory_reset  -m "\"{'ieee_address': '$1', 'channel': '$2' }\""
