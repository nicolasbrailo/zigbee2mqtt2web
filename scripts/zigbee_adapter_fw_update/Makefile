.PHONY: ping flash system_deps

system_deps:
	sudo apt-get install --assume-yes unzip wget

Pipfile: system_deps
	touch Pipfile
	PIPENV_PIPFILE=./Pipfile python3 -m pipenv install pyserial

fw_image:
	wget https://github.com/Koenkk/Z-Stack-firmware/raw/Z-Stack_3.x.0_coordinator_20230507/coordinator/Z-Stack_3.x.0/bin/CC1352P2_CC2652P_launchpad_coordinator_20230507.zip

ping: Pipfile
	PIPENV_PIPFILE=./Pipfile python3 -m pipenv run python ./ping_adapter.py /dev/ttyUSB1

flash: ping 
	@echo "This may be dangerous, run manually:"
	#echo PIPENV_PIPFILE=./Pipfile python3 -m pipenv run python ./cc2538-bsl/cc2538-bsl.py -p /dev/ttyUSB0 -Vvew ./CC2652R_coordinator_20220103.hex

