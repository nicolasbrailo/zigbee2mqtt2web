include ../common.mk

devrun:
	/usr/bin/authbind --deep pipenv run python3 ./main.py

rebuild_ui:
	cat \
		../baticasa_buttons/www/app.js \
		../zmw_contactmon/www/app.js \
		../zmw_heating/www/app.js \
		../zmw_lights/www/debouncedRange.js \
		../zmw_lights/www/light.js \
		../zmw_lights/www/mqtt_lights.js \
		../zmw_reolink_doorbell/www/app.js \
		../zmw_sensormon/www/app.js \
		../zmw_speaker_announce/www/app.js \
		./www/app.js \
		> ./www/app.cat.js
	../zzmw_lib/www/babel_compile_single.sh ./www/app.cat.js ./www/app.rel.js

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install aiohttp
	pipenv install "flask[async]"

