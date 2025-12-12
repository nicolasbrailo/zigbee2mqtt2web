include ../common.mk

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install requests

test_listen:
	mosquitto_sub -v -h 127.0.0.1 -t 'zmw_shelly_plug/#'

