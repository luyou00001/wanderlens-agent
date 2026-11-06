.PHONY: install test models ui

install:
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -e ".[dev]"

test:
	python3 -m pytest

models:
	python3 -m wanderlens models list

ui:
	python3 -m wanderlens ui
