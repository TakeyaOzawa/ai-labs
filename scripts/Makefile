.PHONY: test test-unit test-integration coverage lint fmt verify

PYTHON := python3.12

test:
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest tests/unit/ -m unit

test-integration:
	$(PYTHON) -m pytest tests/integration/ -m integration

coverage:
	$(PYTHON) -m coverage run -m pytest
	$(PYTHON) -m coverage report
	$(PYTHON) -m coverage html

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

fmt:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

verify:
	$(PYTHON) setup/verify-scripts.py
