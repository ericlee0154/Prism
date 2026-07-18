.PHONY: setup dev api web test build clean-data

setup:
	bash scripts/setup.sh

dev:
	bash scripts/dev.sh

api:
	.venv/bin/uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000

web:
	npm run dev

test:
	.venv/bin/python -m pytest -q
	npm test

build:
	npm run build

clean-data:
	@echo "Delete data/prism.duckdb manually if you intentionally want a fresh local ledger."
