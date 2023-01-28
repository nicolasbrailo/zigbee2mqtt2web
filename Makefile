.PHONY: test run install install_system_deps install_service ui restart_and_tail_logs tail_logs

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

install:
	python3 -m pipenv install requests
	# If Redis is missing, it's because it tends to fail when installing spotipy. Try this:
	# python3 -m pipenv --upgrade install spotipy

ui:
	make -C zigbee2mqtt2web_ui all

install_system_deps:
	sudo apt-get --assume-yes install python3-pip authbind python3-autopep8
	make -C zigbee2mqtt2web_extras install_system_deps
	pip3 install pipenv

MKFILE_PATH=$(abspath $(lastword $(MAKEFILE_LIST)))
SRC_DIR=$(patsubst %/,%,$(dir $(MKFILE_PATH)))

install_service:
	@# authbind -> run in port 80 with no root
	sudo touch /etc/authbind/byport/80
	sudo chmod 777 /etc/authbind/byport/80
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
