# Common Makefile targets for all subdirectory projects
# Include this file in subdirectory Makefiles with: include ../common.mk

.PHONY: devrun
devrun:
	pipenv run python3 ./main.py

.PHONY: test
test:
	pipenv run pytest tests/* -v --cov=. --cov-report=term-missing --cov-report=html

.PHONY: rebuild_ui
rebuild_ui:
	../zzmw_lib/www/babel_compile_single.sh ./www/app.js ./www/app.rel.js
	@ln -s ../../zzmw_lib/www/build/rel.css ./www/ || true
	@ln -s ../../zzmw_lib/www/build/extjs ./www/ || true

.PHONY: install_svc
install_svc:
	../scripts/install_svc.sh .

.PHONY: pipenv_rebuild_deps_base
pipenv_rebuild_deps_base:
	rm -f Pipfile Pipfile.lock
	pipenv --rm || true
	pipenv --python python3
	pipenv install -e "$(shell readlink -f "$(PWD)/../zzmw_lib")"
	pipenv install --dev pylint
	pipenv install --dev pytest
	pipenv install --dev pytest-cov

.PHONY: lint
lint: *.py
	echo '' > lint
	pipenv run pylint --max-line-length=120 --disable=C0411 *.py >> lint | true
	cat lint
