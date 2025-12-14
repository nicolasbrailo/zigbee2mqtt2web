.PHONY: test
test:
	pipenv run pytest tests/* -v --cov=. --cov-report=term-missing --cov-report=html

.PHONY: pipenv_rebuild_deps_base
pipenv_rebuild_deps_base:
	rm -f Pipfile Pipfile.lock
	pipenv --rm || true
	pipenv install --dev pylint
	pipenv install --dev pytest
	pipenv install --dev pytest-cov
	@# These are all needed to run tests; the are declared in setup.py, but we don't use setup
	@# when running tests.
	pipenv install apscheduler
	pipenv install flask
	pipenv install inotify-simple
	pipenv install paho-mqtt
	pipenv install systemd-python

.PHONY: lint
lint: *.py
	echo '' > lint
	pipenv run pylint --max-line-length=120 --disable=C0411 *.py >> lint | true
	cat lint
