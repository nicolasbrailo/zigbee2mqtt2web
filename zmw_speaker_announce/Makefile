include ../common.mk

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install flask
	pipenv install aiohttp
	pipenv install soco

test_announce:
	mosquitto_pub -t 'zmw_speaker_announce/tts' -m '{"msg": "test", "lang": "es", "vol": 40}'

test_announce_wwww:
	mosquitto_pub -t 'zmw_speaker_announce/play_asset' -m '{"public_www": "http://bati.casa/web_assets/winxpshutdown.mp3", "vol": 40}'

test_sub_all:
	mosquitto_sub -h 127.0.0.1 -t 'zmw_speaker_announce/#'

test_ping:
	mosquitto_pub -t 'zmw_speaker_announce/ping' -m '{}'

