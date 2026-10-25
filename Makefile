.PHONY: setup up down test egress-check

setup:
	uv sync
	uv run python -m mail_router.data.generate
	@if [ -f models/classifier/model.safetensors ]; then echo "Klassifikator vorhanden, Training übersprungen"; \
	else uv run python -m mail_router.classifier.train --out models/classifier; fi
	docker compose --profile setup run --rm ollama-pull
	docker compose build api

up:
	docker compose up -d --build --wait

down:
	docker compose down

test:
	uv run pytest

egress-check:
	./scripts/check_egress.sh
