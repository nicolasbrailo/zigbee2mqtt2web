include ../common.mk

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install -e "$(shell readlink -f "$(PWD)/../zext_libs/PyTelegramBot")"
	pipenv install requests

test_send_photo:
	mosquitto_pub -t 'zmw_telegram/send_photo' -m '{"path": "/home/batman/src/BatiCasa/web_assets/doorbell_snap.jpg", "msg": "HOLA"}'

test_send_text:
	mosquitto_pub -t 'zmw_telegram/send_text' -m '{"msg": "HOLA"}'

test_reg_cmds:
	mosquitto_pub -t 'zmw_telegram/register_command' -m '{"cmd": "mqtt_ping", "descr": "Test mqtt proxy"}'

test_listen_all:
	mosquitto_sub -h 127.0.0.1 -t 'zmw_telegram/#'

test_listen_cmds:
	mosquitto_sub -h 127.0.0.1 -t 'zmw_telegram/on_command/mqtt_ping'

