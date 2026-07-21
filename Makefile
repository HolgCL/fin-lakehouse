.PHONY: setup ingest build test lint demo

setup:
	uv sync

ingest:
	@echo "ingest: not implemented yet (milestone 1)" && exit 1

build:
	@echo "build: not implemented yet (milestone 3)" && exit 1

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run mypy src/

demo:
	@echo "demo: not implemented yet (milestone 6)" && exit 1
