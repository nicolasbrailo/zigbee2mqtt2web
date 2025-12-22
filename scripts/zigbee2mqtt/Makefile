
ota_update:
	echo "Use this to update a device with friendlyname or ID XXX"
	echo mosquitto_pub -t zigbee2mqtt/bridge/request/device/ota_update/update -m '{"id": "'XXX'"}'

kick_device:
	echo "This will make a device unknown to zigbee2mqtt, forcing an interview to happen. Use ID, not friendly name."
	echo "mosquitto_pub -t zigbee2mqtt/bridge/request/device/remove -m \"{'id': 'XXX','force':true}\""

touchlink_ident:
	echo mosquitto_pub -t zigbee2mqtt/bridge/request/touchlink/identify -m '{"ieee_address": "'ADDR'", "channel": 'CH' }'

touchlink_factory_reset:
	echo mosquitto_pub -t zigbee2mqtt/bridge/request/touchlink/factory_reset  -m''

touchlink_scan:
	mosquitto_pub -t 'zigbee2mqtt/bridge/request/touchlink/scan' -m ''
	journalctl -f -u zigbee2mqtt.service | grep touchlink/scan

