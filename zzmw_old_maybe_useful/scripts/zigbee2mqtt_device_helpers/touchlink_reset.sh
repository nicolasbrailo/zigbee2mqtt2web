#!/usr/bin/bash
set -euo pipefail
echo "This will factory reset a device in range, identified with touchlink_identify. If sure, exec cmd below."
echo "Note that this command may reset a random device, even if an address is specified, so ensure only the devices you need to reset are in range"
echo mosquitto_pub -t zigbee2mqtt/bridge/request/touchlink/factory_reset  -m''
