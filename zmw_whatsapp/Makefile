include ../common.mk

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install requests
	pipenv install flask

test_send:
	mosquitto_pub -t 'zmw_whatsapp/send_photo' -m '{"path": "/home/batman/src/BatiCasa/web_assets/doorbell_snap.jpg", "msg": "HOLA"}'

