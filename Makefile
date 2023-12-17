.PHONY: test run shell install ui restart_and_tail_logs tail_logs ssl reinstall_pipenv_deps

test:
	python3 -m pipenv run python -m unittest tests/*

run: system_has_dep_svcs
	python3 -m pipenv run python ./main.py | tee run.log

shell:
	python3 -m pipenv run python

lint.log:
	autopep8 -r --in-place --aggressive --aggressive zigbee2mqtt2web/ | tee lint.log
	python3 -m pipenv run python -m pylint zigbee2mqtt2web --disable=C0411 | tee --append lint.log
	autopep8 -r --in-place --aggressive --aggressive zigbee2mqtt2web_extras/ | tee --append lint.log
	python3 -m pipenv run python -m pylint zigbee2mqtt2web_extras --disable=C0411 | tee --append lint.log

ui:
	make -C zigbee2mqtt2web_ui all

Pipfile:
	@if [ "$(shell arch)" = "x86_64" ]; then \
		cp Pipfile.x86 Pipfile; \
	else \
		echo 'You need to `mv Pipfile.arm Pipfile` or `mv Pipfile.x86 Pipfile` first'; \
		false; \
	fi

install: Pipfile
	python3 -m pipenv --python $(shell which python3)
	python3 -m pipenv install requests

reinstall_pipenv_deps:
	@echo "This is a list of the pipenv install commands I've used to get stuff working"
	@echo "It may or may not be stable, and it may or may not be complete (probably isn't)"
	@echo "Use this to create a new environment from scratch."
	#python3 -m pipenv install apscheduler
	#python3 -m pipenv install astral
	#python3 -m pipenv install git+https://github.com/ReolinkCameraAPI/reolink-python-api.git
	#python3 -m pipenv install git+https://github.com/ReolinkCameraAPI/reolink-python-api.git#egg=reolink-python-api
	#python3 -m pipenv install pyftpdlib
	#python3 -m pipenv install requests
	#python3 -m pipenv install soco
	#python3 -m pipenv install spotipy --upgrade
	# If Redis is missing, it's because it tends to fail when installing spotipy. Try this a few times:
	#python3 -m pipenv --upgrade install spotipy
	# Required for https mode (which is required to have the webapp access the mic)
	# May not work nicely in an rpi
	#python3 -m pipenv install pyopenssl

restart_and_tail_logs:
	sudo systemctl restart zigbee2mqtt2web.service && journalctl -fu zigbee2mqtt2web

tail_logs:
	journalctl -fu zigbee2mqtt2web

ssl: zmw.key zmw.cert
zmw.key zmw.cert:
	openssl req -nodes -new -x509 -keyout zmw.key -out zmw.cert
	#openssl genrsa -des3 -out server.key 1024
	#openssl req -new -key server.key -out server.csr
	#cp server.key server.key.org
	#openssl rsa -in server.key.org -out server.key
	#openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt


.PHONY: install_system_deps install_services system_has_dep_svcs

install_system_deps:
	sudo apt-get --assume-yes install python3-pip pipenv authbind python3-autopep8
	make -C zigbee2mqtt2web_extras install_system_deps
	make -C zigbee2mqtt2web_ui install_system_deps

install_services:
	./scripts/install_svcs.sh

system_has_dep_svcs: mosquitto.service zigbee2mqtt.service

%.service:
	@if [ $(shell systemctl is-active --quiet $@) ]; then \
		true; \
	else \
		echo "\033[0;31m"; \
		echo "System seems to be missing $@. Run 'make install_services' for help."; \
		echo "If service is installed in a way this Makefile can't find, do 'touch $@'"; \
		echo "\033[0m"; \
		false; \
	fi
