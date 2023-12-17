.PHONY: ping flash

ADAPTER_DEV=$(shell ls /dev/ttyUSB*)

FW_IMG=CC1352P2_CC2652P_launchpad_coordinator_20230507

Pipfile:
	sudo apt-get install --assume-yes unzip wget
	touch Pipfile
	PIPENV_PIPFILE=./Pipfile python3 -m pipenv install pyserial intelhex python-magic

$(FW_IMG).hex:
	wget https://github.com/Koenkk/Z-Stack-firmware/raw/Z-Stack_3.x.0_coordinator_20230507/coordinator/Z-Stack_3.x.0/bin/$(FW_IMG).zip
	unzip $(FW_IMG).zip
	rm $(FW_IMG).zip

ping: Pipfile
	PIPENV_PIPFILE=./Pipfile python3 -m pipenv run python ./ping_adapter.py $(ADAPTER_DEV)

flash: ping $(FW_IMG).hex
	@echo "This may be dangerous, run manually:"
	@echo PIPENV_PIPFILE=./Pipfile python3 -m pipenv run python ./cc2538-bsl/cc2538-bsl.py -p $(ADAPTER_DEV) -Vvew $(FW_IMG).hex

