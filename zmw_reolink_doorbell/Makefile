include ../common.mk

rebuild_ui_nvr:
	../zzmw_lib/www/babel_compile_single.sh ./www/nvr.js ./www/nvr.rel.js

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install -e "$(shell readlink -f "$(PWD)/../zext_libs/reolink_aio")"
	pipenv install flask
	pipenv install apscheduler

test_mosquitto_sub:
	mosquitto_sub -h 127.0.0.1 -t 'zmw_reolink_doorbell/#'

test_mqtt_snap:
	mosquitto_pub -t 'zmw_reolink_doorbell/snap' -m '{}'

test_mqtt_rec:
	mosquitto_pub -t 'zmw_reolink_doorbell/rec' -m '{"secs": 5}'

