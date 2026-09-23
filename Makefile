# Pychestrate core -- developer entry points.
#
# Run 'make' (or 'make help') for the list of targets. Every target that
# appears in the help carries a '## description' on its rule line, and
# '##@ Section' lines group them; add both when you add a target.
#
# Tools come from the repository virtual environment ($(VENV), created by
# 'make setup'), never from whatever python is first on PATH.

.DEFAULT_GOAL := help
SHELL := /bin/bash

VENV     ?= .venv
PYTHON   := $(VENV)/bin/python
TESTBASE := $(VENV)/bin/testbase

# The test root's top-level package ('ccai' after the namespace rename,
# 'automojo' before it).
TEST_ROOT      ?= $(firstword $(wildcard source/testroots/ccai source/testroots/automojo))
TEST_NAMESPACE := $(notdir $(TEST_ROOT))
TEST_SUITE     := $(TEST_NAMESPACE).tests.pychestrate.singlehost

# Python path for running code and tests straight from the source tree.
SOURCE_PYTHONPATH := source/packages:source/testroots

.PHONY: help setup test lint

##@ Help

help: ## Show this list of targets (the default)
	@echo "usage: make <target> [VAR=value ...]"
	@awk 'BEGIN {FS = ":.*## "} \
	     /^##@ / {printf "\n%s\n", substr($$0, 5)} \
	     /^[a-zA-Z0-9_-]+:.*## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo

##@ Development

setup: ## Create or refresh .venv with poetry (development/setup-environment)
	./development/setup-environment

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
#
# testbase has two silent traps, both avoided here (and flagged by 'make lint'):
#
#   * An --includes value is a string prefix, so it also runs every module
#     whose name merely starts with it.
#   * --excludes does nothing: no test is ever excluded.
#
# development/select-tests turns SELECT / EXCLUDE into one exact --includes
# per module. With neither, the whole single-host suite runs. Selectors are
# relative to <namespace>.tests.pychestrate.singlehost or absolute.

SELECT      ?=
EXCLUDE     ?=
TEST_OUTPUT ?= .output/test-$(shell date +%Y%m%d-%H%M%S)

##@ Quality

test: ## Run single-host tests: [SELECT="core.storage"] [EXCLUDE=...] [TEST_OUTPUT=dir]
	@test -n "$(TEST_ROOT)" || { echo "make test: no test root under source/testroots" >&2; exit 2; }
	@includes="$$($(PYTHON) development/select-tests --root $(TEST_ROOT) --suite $(TEST_SUITE) \
	    --base $(TEST_SUITE) --base $(TEST_NAMESPACE).tests.pychestrate --base $(TEST_NAMESPACE).tests \
	    $(foreach s,$(SELECT),--select $(s)) $(foreach x,$(EXCLUDE),--exclude $(x)))" || exit 2; \
	mkdir -p "$(TEST_OUTPUT)"; \
	echo "testbase: $$(echo "$$includes" | wc -l) include(s); output in $(TEST_OUTPUT)"; \
	PYTHONPATH="$(SOURCE_PYTHONPATH)$${PYTHONPATH:+:$$PYTHONPATH}" \
	    $(TESTBASE) testing run --root $(TEST_ROOT) $$includes --output="$(TEST_OUTPUT)" \
	    > "$(TEST_OUTPUT).log" 2>&1; \
	$(TESTBASE) agents summary extract --summary-file "$(TEST_OUTPUT)/testrun_summary.json"; \
	if ! grep -q '"result": "PASSED"' "$(TEST_OUTPUT)/testrun_summary.json" 2>/dev/null; then \
	    $(TESTBASE) agents testresult failures --results-file "$(TEST_OUTPUT)/testrun_results_stream.jsos" | head -80; \
	    echo "make test: FAILED (log: $(TEST_OUTPUT).log)" >&2; exit 1; \
	fi

lint: ## Static checks: Python syntax and testbase command traps
	$(PYTHON) development/lint
