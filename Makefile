# Auto-discover all subdirectories with Makefiles
LINT_DIRS := $(patsubst %/Makefile,%,$(wildcard */Makefile))

.PHONY: systemdeps
systemdeps:
	sudo apt-get install -y python3-pkgconfig libsystemd-dev pylint autopep8

.PHONY: test
test:
	@echo "Running test on all projects..."
	@for dir in $(LINT_DIRS); do \
		make -C $$dir test || true; \
	done

.PHONY: lint
lint:
	@echo "Running lint on all projects..."
	@for dir in $(LINT_DIRS); do \
		make -C $$dir lint || true; \
	done
	@for dir in $(LINT_DIRS); do \
		if [ -f $$dir/lint ]; then \
			score=$$(grep "rated at" $$dir/lint | tail -1); \
			if [ -n "$$score" ]; then \
				printf "%-30s %s\n" "$$dir:" "$$score"; \
			fi; \
		fi; \
	done

.PHONY: cat-lints
cat-lints:
	@for dir in $(LINT_DIRS); do \
		if [ -f $$dir/lint ]; then \
			echo "==================== $$dir ===================="; \
			cat $$dir/lint; \
		fi; \
	done

