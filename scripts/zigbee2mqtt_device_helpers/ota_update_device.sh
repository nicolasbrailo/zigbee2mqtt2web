echo "Updating device with friendlyname or ID $1"
mosquitto_pub -t zigbee2mqtt/bridge/request/device/ota_update/update -m '{"id": "'$1'"}'
