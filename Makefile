VENV = .venv
BIN = $(VENV)/bin

.PHONY: help lint format run clean install typecheck pre-commit

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies (including dev tools)"
	@echo "  make lint       - Run ruff linter"
	@echo "  make format     - Run ruff formatter"
	@echo "  make typecheck  - Run mypy type checker (optional)"
	@echo "  make pre-commit - Run ruff lint + format check"
	@echo "  make run        - Run the scraper"
	@echo "  make clean      - Clean generated files"

install:
	uv pip install -e .
	uv pip install ruff mypy pre-commit typer rich

lint:
	$(BIN)/ruff check cultural_scraper

format:
	$(BIN)/ruff format cultural_scraper

typecheck:
	$(BIN)/mypy cultural_scraper

pre-commit:
	$(BIN)/ruff check cultural_scraper && $(BIN)/ruff format --check cultural_scraper

run:
	python -m cultural_scraper.cli.main scrape -c cultural_scraper/config/config.yaml

clean:
	rm -rf output/*.html
	rm -rf cultural_scraper/**/__pycache__
	rm -rf tests/__pycache__
	rm -rf .pytest_cache
	find . -name "*.pyc" -delete
