echo "This will make a device unknown to zigbee2mqtt, forcing an interview to happen"
echo "Danger: Deletes info from your config. Uncomment code below to use or copypaste:"
echo "mosquitto_pub -t zigbee2mqtt/bridge/request/device/remove -m {'id': '$1','force':true}"
# mosquitto_pub -t zigbee2mqtt/bridge/request/device/remove -m {"id": "$1","force":true}
