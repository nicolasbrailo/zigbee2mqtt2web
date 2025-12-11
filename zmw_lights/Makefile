include ../common.mk

.PHONY: rebuild_ui
rebuild_ui:
	cat ./www/debouncedRange.js ./www/light.js ./www/mqtt_lights.js > ./www/app.big.js
	../zzmw_lib/www//babel_compile_single.sh ./www/app.big.js ./www/app.rel.js

old:
	../zzmw_lib/www//babel_compile_single.sh ./www/debouncedRange.js ./www/debouncedRange.rel.js
	../zzmw_lib/www//babel_compile_single.sh ./www/light.js ./www/light.rel.js
	cat ./www/debouncedRange.rel.js ./www/light.rel.js ./www/mqtt_lights.rel.js > ./www/app.rel.js
	rm ./www/debouncedRange.rel.js ./www/light.rel.js ./www/mqtt_lights.rel.js

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install -e "$(shell readlink -f "$(PWD)/../zz2m")"

