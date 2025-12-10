include ../common.mk

.PHONY: rebuild_ui
rebuild_ui:
	../zzmw_lib/www//babel_compile_single.sh ./www/debouncedRange.js ./www/debouncedRange.rel.js
	../zzmw_lib/www//babel_compile_single.sh ./www/light.js ./www/light.rel.js
	../zzmw_lib/www//babel_compile_single.sh ./www/mqtt_lights.js ./www/mqtt_lights.rel.js
	cat ./www/debouncedRange.rel.js ./www/light.rel.js ./www/mqtt_lights.rel.js > ./www/app.rel.js
	rm ./www/debouncedRange.rel.js ./www/light.rel.js ./www/mqtt_lights.rel.js
	@ln -s ../../zzmw_lib/www/build/rel.css ./www/ || true
	@ln -s ../../zzmw_lib/www/build/extjs ./www/ || true

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install -e "$(shell readlink -f "$(PWD)/../zz2m")"

