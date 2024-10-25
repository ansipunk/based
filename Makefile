.PHONY: help bootstrap lint test clean
DEFAULT: help

VENV = .venv
PYTHON = $(VENV)/bin/python

help:
	@echo "Available targets:"
	@echo "  bootstrap - setup development environment"
	@echo "  lint      - run static code analysis"
	@echo "  test      - run project tests"
	@echo "  clean     - clean environment and remove development artifacts"

bootstrap:
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip==24.2 setuptools==75.2.0 wheel==0.44.0
	$(PYTHON) -m pip install -e .[postgres,sqlite,dev]

lint: $(VENV)
	$(PYTHON) -m ruff check based tests
	$(PYTHON) -m mypy --strict based

test: $(VENV)
	$(PYTHON) -m pytest

clean:
	rm -rf $(VENV) .coverage .mypy_cache .pytest_cache .ruff_cache htmlcov based.egg-info coverage.xml
	find . -type d -name "__pycache__" | xargs rm -rf
