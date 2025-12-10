include ../common.mk

rebuild_deps: pipenv_rebuild_deps_base
	pipenv install apscheduler
	pipenv install -e "$(shell readlink -f "$(PWD)/../zz2m")"

