.PHONY: test
test:
	pipenv run pytest z2m/tests/* -v --cov=. --cov-report=term-missing --cov-report=html

.PHONY: pipenv_rebuild_deps_base
pipenv_rebuild_deps_base:
	rm -f Pipfile Pipfile.lock
	pipenv --rm || true
	pipenv install --dev pylint
	pipenv install --dev pytest
	pipenv install --dev pytest-cov

.PHONY: lint
lint: *.py
	echo '' > lint
	pipenv run pylint --max-line-length=120 --disable=C0411 *.py >> lint | true
	cat lint
