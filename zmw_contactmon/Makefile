include ../common.mk

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install -e "$(shell readlink -f "$(PWD)/../zz2m")"

# Test targets - simulate contact sensor events
door_open:
	mosquitto_pub -h localhost -p 1883 -t 'zigbee2mqtt/ContactSensor_FrontDoor' -m '{"contact": false}'
door_close:
	mosquitto_pub -h localhost -p 1883 -t 'zigbee2mqtt/ContactSensor_FrontDoor' -m '{"contact": true}'
window_open:
	mosquitto_pub -h localhost -p 1883 -t 'zigbee2mqtt/ContactSensor_BathroomWindow' -m '{"contact": false}'
window_close:
	mosquitto_pub -h localhost -p 1883 -t 'zigbee2mqtt/ContactSensor_BathroomWindow' -m '{"contact": true}'

