.PHONY: setup ingest build test lint demo

setup:
	uv sync

ingest:
	uv run python -m fin_lakehouse.ingest KHC

build:
	@echo "build: not implemented yet (milestone 3)" && exit 1

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run mypy src/

demo:
	@echo "demo: not implemented yet (milestone 6)" && exit 1
