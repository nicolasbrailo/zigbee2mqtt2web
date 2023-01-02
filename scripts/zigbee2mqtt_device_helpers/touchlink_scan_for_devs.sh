echo "Scanning..."
mosquitto_pub -t 'zigbee2mqtt/bridge/request/touchlink/scan' -m ''
sleep 10
journalctl -u zigbee2mqtt.service | grep touchlink/scan


