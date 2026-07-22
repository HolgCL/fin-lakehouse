.PHONY: setup ingest build report test lint demo

setup:
	uv sync

ingest:
	uv run python -m fin_lakehouse.ingest

build:
	uv run python -m fin_lakehouse.build_silver
	cd transform && uv run dbt build --profiles-dir profiles

report:
	uv run python -m fin_lakehouse.report

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run mypy src/

demo:
	uv run streamlit run dashboards/app.py
