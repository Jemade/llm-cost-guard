# LLM Cost Guard

[![CI](https://github.com/Jemade/llm-cost-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/Jemade/llm-cost-guard/actions/workflows/ci.yml)

A Python service for estimating model-request costs, tracking token usage, and checking daily, weekly, and monthly budgets before a request proceeds.

## Features

- Configurable model pricing and token-based estimates.
- Budget limits and expiring spend reservations.
- Usage recording and reservation reconciliation.
- Threshold alerts with an optional webhook.
- FastAPI endpoints and a usage dashboard.
- SQLAlchemy persistence with PostgreSQL or SQLite.

## Run with Docker

```bash
git clone https://github.com/Jemade/llm-cost-guard.git
cd llm-cost-guard
docker compose up --build
```

Open http://localhost:8000/dashboard or http://localhost:8000/docs. Compose starts the API and PostgreSQL.

## Run locally

Requires Python and the packages in `requirements.txt`. The command below selects SQLite for local development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite+aiosqlite:///./costguard.db
uvicorn app.main:app --reload --port 8000
```

Set configuration through `.env` or environment variables. See `.env.example` for budget limits, reservation expiry, pricing-file location, and the optional alert webhook. Run `python -m app.cli.seed` only when you want demonstration data.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Documentation

- [Architecture](docs/architecture.md)
- [Budget enforcement](docs/budget-enforcement.md)
- [Pricing](docs/pricing.md)
- [Demo](docs/demo.md)

## Current scope

Prices come from the configured pricing file and must be maintained. Token estimates and reserved cost are estimates; recorded usage reconciles them with supplied actual usage. Applications must integrate the budget checks into their request path for enforcement.
