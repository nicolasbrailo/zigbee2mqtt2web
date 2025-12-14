include ../common.mk

.PHONY: oldrebuild_ui
oldrebuild_ui:
	cat ./www/debouncedRange.js ./www/light.js ./www/mqtt_lights.js > ./www/app.big.js
	../zzmw_lib/www//babel_compile_single.sh ./www/app.big.js ./www/app.rel.js

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install -e "$(shell readlink -f "$(PWD)/../zz2m")"

