.PHONY: test run install install_system_deps install_service ui restart_and_tail_logs tail_logs ssl

test:
	python3 -m pipenv run python -m unittest tests/*

run:
	python3 -m pipenv run python ./main.py | tee run.log

shell:
	python3 -m pipenv run python

lint:
	autopep8 -r --in-place --aggressive --aggressive zigbee2mqtt2web/ | tee lint.log
	python3 -m pipenv run python -m pylint zigbee2mqtt2web --disable=C0411 | tee --append lint.log
	autopep8 -r --in-place --aggressive --aggressive zigbee2mqtt2web_extras/ | tee --append lint.log
	python3 -m pipenv run python -m pylint zigbee2mqtt2web_extras --disable=C0411 | tee --append lint.log

Pipfile:
	echo "Select one of Pipfile.arm or Pipfile.x86, and mv to Pipfile"
	false

install: Pipfile
	python3 -m pipenv --python $(shell which python3 )
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

ui:
	make -C zigbee2mqtt2web_ui all

install_system_deps:
	sudo apt-get --assume-yes install python3-pip authbind python3-autopep8
	make -C zigbee2mqtt2web_extras install_system_deps
	make -C zigbee2mqtt2web_ui install_system_deps
	pip3 install pipenv

MKFILE_PATH=$(abspath $(lastword $(MAKEFILE_LIST)))
SRC_DIR=$(patsubst %/,%,$(dir $(MKFILE_PATH)))

install_service:
	@# authbind -> run in port 80 with no root
	sudo touch /etc/authbind/byport/80
	sudo chmod 777 /etc/authbind/byport/80
	sudo touch /etc/authbind/byport/443
	sudo chmod 777 /etc/authbind/byport/443
	cat ./scripts/zigbee2mqtt2web.service.template | \
		sed "s|#INSTALL_DIR#|$(SRC_DIR)|g" | \
		sudo tee >/dev/null /etc/systemd/system/zigbee2mqtt2web.service
	sudo systemctl stop zigbee2mqtt2web | true
	sudo systemctl daemon-reload
	sudo systemctl enable zigbee2mqtt2web
	sudo systemctl start zigbee2mqtt2web
	sudo systemctl status zigbee2mqtt2web

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

