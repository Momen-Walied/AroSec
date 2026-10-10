# Vigilance Data Foundation — developer commands.
# Run `make help` for the list.

PY ?= python
VENV ?= .venv
BIN := $(VENV)/bin

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: ## Create venv and install dev dependencies (requires uv)
	uv venv --python 3.12 $(VENV)
	uv pip install -e ".[dev,pcap]" --python $(BIN)/python
	@echo "Activate with: source $(BIN)/activate"

.PHONY: inspect
inspect: ## Inspect all datasets (status + structure)
	$(BIN)/python -m src.cli datasets inspect

.PHONY: download-sample
download-sample: ## Download all automatically-available datasets in sample mode
	DATA_MODE=sample $(BIN)/python -m src.cli datasets download --all --mode sample

.PHONY: normalize
normalize: ## Normalize all available datasets end-to-end
	$(BIN)/python -m src.cli datasets normalize --all

.PHONY: graph
graph: ## Build the temporal graph + feature windows at the default window
	$(BIN)/python -m src.cli build-graph --all --window $(shell grep -E '^DEFAULT_WINDOW' .env 2>/dev/null | cut -d= -f2 || echo 30s)

.PHONY: validate
validate: ## Run schema + data-quality validation
	$(BIN)/python -m src.cli validate

.PHONY: report
report: ## Regenerate all markdown reports
	$(BIN)/python -m src.cli report

.PHONY: test
test: ## Run the test suite
	$(BIN)/python -m pytest

.PHONY: lint
lint: ## Lint with ruff
	$(BIN)/ruff check src tests

.PHONY: e2e
e2e: ## Full end-to-end demo pipeline on the sample data
	$(BIN)/python -m src.cli demo

.PHONY: clean
clean: ## Remove caches and interim outputs (keeps raw + processed)
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache data/interim/*
