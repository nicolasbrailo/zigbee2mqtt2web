include ../common.mk

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install soco flask-sock

sub_all:
	mosquitto_sub -v -h localhost -p 1883 -t 'zmw_sstest/#' -v

test_switch_source:
	mosquitto_pub -h localhost -p 1883 -t 'zmw_sstest/switch_source' -m '{"source": "spotify"}'

test_switch_linein:
	mosquitto_pub -h localhost -p 1883 -t 'zmw_sstest/switch_source' -m '{"source": "line-in"}'

