include ../common.mk

devrun:
	/usr/bin/authbind --deep pipenv run python3 ./main.py

rebuild_ui:
	@ln -s ../../zzmw_lib/www/build/rel.css ./www/ || true
	@ln -s ../../zzmw_lib/www/build/extjs ./www/ || true
	../zzmw_lib/www/babel_compile_single.sh ../zmw_reolink_doorbell/www/app.js ./www/doorbell_cam.rel.js
	../zzmw_lib/www/babel_compile_single.sh ../zmw_lights/www/debouncedRange.js ./www/debouncedRange.rel.js
	../zzmw_lib/www/babel_compile_single.sh ../zmw_lights/www/light.js ./www/light.rel.js
	../zzmw_lib/www/babel_compile_single.sh ../zmw_lights/www/mqtt_lights.js ./www/mqtt_lights.rel.js
	../zzmw_lib/www/babel_compile_single.sh ../zmw_speaker_announce/www/app.js ./www/speaker_announce.rel.js
	../zzmw_lib/www/babel_compile_single.sh ../zmw_contactmon/www/app.js ./www/contact_mon.rel.js
	../zzmw_lib/www/babel_compile_single.sh ../zmw_heating/www/app.js ./www/heating.rel.js
	../zzmw_lib/www/babel_compile_single.sh ../zmw_sensormon/www/app.js ./www/sensor_mon.rel.js
	../zzmw_lib/www/babel_compile_single.sh ../baticasa_buttons/www/app.js ./www/baticasa_buttons.rel.js
	../zzmw_lib/www/babel_compile_single.sh ./www/app.js ./www/app.tmp.rel.js
	# Concatenate everything together
	cat ./www/debouncedRange.rel.js \
	    ./www/light.rel.js \
	    ./www/mqtt_lights.rel.js \
	    ./www/speaker_announce.rel.js \
	    ./www/contact_mon.rel.js \
	    ./www/doorbell_cam.rel.js \
	    ./www/heating.rel.js \
	    ./www/sensor_mon.rel.js \
	    ./www/baticasa_buttons.rel.js \
	    ./www/app.tmp.rel.js > ./www/app.rel.js
	# Clean up temp files
	rm ./www/debouncedRange.rel.js \
	   ./www/light.rel.js ./www/mqtt_lights.rel.js ./www/contact_mon.rel.js ./www/sensor_mon.rel.js \
	   ./www/speaker_announce.rel.js ./www/app.tmp.rel.js ./www/heating.rel.js \
	   ./www/doorbell_cam.rel.js ./www/baticasa_buttons.rel.js 

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install aiohttp
	pipenv install "flask[async]"

