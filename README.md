# LLM Cost Guard

[![CI](https://github.com/jemade/llm-cost-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/jemade/llm-cost-guard/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00.svg)](https://www.sqlalchemy.org/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)

> Production-grade LLM token cost estimation, usage tracking, and concurrency-safe budget control system for AI applications and multi-agent platforms.

---

## Problem

LLM APIs have variable and asymmetric pricing across providers, models, and token types (prompt tokens vs completion tokens vs reasoning tokens). 

In production AI applications, engineering teams face critical operational questions:
1. **Pre-flight Estimation**: *How many tokens will this prompt use, and what will it cost before sending it?*
2. **Budget Protection**: *Can the system block an expensive request before it reaches the provider if it would exceed our remaining budget?*
3. **Usage Observability**: *How much have we spent today, this week, and this month across users, models, and endpoints?*
4. **Concurrency Safety**: *What happens when two concurrent requests arrive simultaneously against a tight remaining budget?*

LLM Cost Guard solves these problems by providing an automated financial control plane that estimates costs, enforces configurable daily/weekly/monthly budgets with concurrency safety, tracks actual usage, and dispatches threshold alerts.

---

## Why This Exists

Most LLM cost tracking is **post-hoc**: you receive an alert or an invoice hours or days after an agent loop runs wild or an expensive model is accidentally called at scale.

LLM Cost Guard operates as a **pre-flight interceptor**:
- It estimates input and expected output costs **before** provider calls are made.
- It determines `ALLOW` or `BLOCK` within milliseconds based on real-time database state.
- It employs pessimistic row locks and atomic budget reservations to prevent concurrent race conditions.
- It separates estimated costs from actual costs without overwriting historical records.

---

## Architecture

```mermaid
graph TD
    subgraph Client Application
        Agent[AI Agent / Application Service]
    end

    subgraph LLM Cost Guard Plane
        API[FastAPI Gateway]
        Catalog[Pricing Catalog YAML]
        Estimator[Token Estimator]
        Calculator[Cost Calculator]
        BudgetSvc[Budget & Concurrency Service]
        AlertSvc[Alert Service]
    end

    subgraph Data Tier
        DB[(PostgreSQL 16)]
    end

    subgraph Downstream
        Provider[LLM Provider API<br>OpenAI / Anthropic / Google / DeepSeek]
        Webhook[Alert Webhook<br>Slack / Discord / Webhook]
    end

    Agent -->|1. POST /v1/cost/check (reserve=true)| API
    API -->|Read model rates| Catalog
    API -->|Compute input tokens| Estimator
    API -->|Compute exact USD| Calculator
    API -->|Pessimistic Lock & Reserve| BudgetSvc
    BudgetSvc -->|Check period spend + reservations| DB
    BudgetSvc -->|Evaluate limits| API
    
    API -->|2. ALLOW or BLOCK| Agent
    
    Agent -.->|3. If ALLOW: Execute request| Provider
    Agent -->|4. POST /v1/usage (record actual & commit hold)| API
    API -->|Persist log & commit reservation| DB
    DB -->|Evaluate thresholds: 80%, 90%, 100%| AlertSvc
    AlertSvc -->|Console & HTTP POST| Webhook
```

---

## How Cost Estimation Works

The system strictly decouples **token estimation** from **cost calculation**:

1. **Token Estimation (`TokenEstimator`)**:
   - **OpenAI Models**: Uses official `tiktoken` byte-pair encodings (`o200k_base` for GPT-4o, o1, o3-mini; `cl100k_base` for GPT-4). Calculates exact ChatML formatting tokens (~3 tokens per message + 3 priming tokens). Marked with `confidence: "exact"`.
   - **Anthropic Claude**: Claude models use a proprietary BPE tokenizer. The estimator applies a calibrated ratio (~1.08x of `cl100k_base`) with explicit metadata disclosure (`confidence: "approximation"`).
   - **Google Gemini**: Gemini uses SentencePiece. The estimator applies a calibrated character-to-token heuristic (~4.0 chars/token in English) with `confidence: "approximation"`.
   - **DeepSeek**: Uses a 128k byte-level BPE baseline with `confidence: "approximation"`.

2. **Cost Calculation (`CostCalculator`)**:
   - Computes input and output costs using Python `Decimal` arithmetic rounded to 6 decimal places (\$0.000001 micro-dollars):
     $$\text{Cost} = \left(\frac{\text{Input Tokens}}{1,000,000} \times \text{Input Rate}\right) + \left(\frac{\text{Output Tokens}}{1,000,000} \times \text{Output Rate}\right)$$
   - Pure estimation: **the system never calls the downstream LLM API merely to estimate cost**.

---

## Pricing Model

Model rates are maintained in [`config/pricing.yaml`](config/pricing.yaml) and can be updated without code changes or redeployments:

```yaml
- provider: "openai"
  model: "gpt-4o"
  tokenizer_type: "tiktoken"
  encoding_name: "o200k_base"
  input_cost_per_1m_tokens: 2.50
  output_cost_per_1m_tokens: 10.00
  currency: "USD"
  effective_date: "2024-08-06"
  last_verified: "2025-01-15"
```

If a requested model is missing, the API returns `404 Not Found` with a clear explanation (`ModelPricingNotFoundError`). Historical usage records store immutable snapshots of costs, ensuring price updates never corrupt past financial reports.

---

## Budget Enforcement

Budgets support three concurrent calendar windows calculated strictly in UTC:
- **Daily**: Resets at `00:00:00 UTC` daily.
- **Weekly**: Resets at `00:00:00 UTC` on Monday.
- **Monthly**: Resets at `00:00:00 UTC` on the 1st of the month.

### Concurrency Safety Strategy

When multiple requests arrive concurrently:
1. **Row-Level Pessimistic Locks**: The budget transaction locks the target `budget_configs` row (`SELECT ... FOR UPDATE`), serializing concurrent checks.
2. **In-Flight Reservations**: When `reserve=True` is supplied, an atomic hold is placed in `budget_reservations` with a 60-second TTL.
3. Subsequent requests evaluate `spent + active_reservations + estimated_cost`. If the total exceeds the budget, the second request is **BLOCKED**.
4. Once the LLM call completes, the client posts to `/v1/usage` with the `reservation_id`, which commits the reservation and records the actual cost.

---

## Alerting

- **Configurable Thresholds**: Default `80%`, `90%`, `100%`.
- **Deduplication**: Backed by a unique database constraint `(scope, period_type, period_start, threshold)`. The system will **never spam** the same threshold alert within the same period window.
- **Dispatchers**:
  - **Console**: High-visibility structured log alerts.
  - **Webhook**: Real HTTP POST dispatch (Slack/Discord compatible payload) with retry and timeout via `httpx`.

---

## Dashboard

A lightweight, modern web dashboard is served directly at `/dashboard`:
- Real-time spend metrics (Total, Daily, Weekly, Monthly) with visual budget progress gauges.
- Spend breakdown by model (spend, token counts, request volume).
- Spend breakdown by endpoint.
- Recent requests table with status badges (SUCCESS, BLOCKED, FAILED), latencies, and token numbers.
- Auto-refresh toggle and manual refresh button.

---

## API

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health and database connectivity check. |
| `POST` | `/v1/estimate` | Pre-flight token and cost estimation. |
| `POST` | `/v1/cost/check` | Pre-flight dry-run check returning `ALLOW` or `BLOCK`. |
| `POST` | `/v1/usage` | Record actual LLM usage and commit budget reservations. |
| `GET` | `/v1/usage` | Query historical usage logs with filters and pagination. |
| `GET` | `/v1/budgets` | List configured budgets and current spending. |
| `POST` | `/v1/budgets` | Create or update budget limits and alert thresholds. |
| `GET` | `/v1/alerts` | List triggered alert events. |
| `GET` | `/metrics` | Structured operational metrics for Prometheus/monitoring. |

Interactive OpenAPI documentation is available at `/docs`.

---

## Example

### 1. Pre-flight Token & Cost Estimation
```bash
curl -s -X POST http://localhost:8000/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o",
    "prompt": "Explain quantum computing in three concise sentences.",
    "expected_output_tokens": 80
  }'
```

**Response**:
```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "estimated_input_tokens": 12,
  "estimated_output_tokens": 80,
  "estimated_total_tokens": 92,
  "estimated_input_cost": 0.00003,
  "estimated_output_cost": 0.0008,
  "estimated_total_cost": 0.00083,
  "currency": "USD",
  "tokenizer_type": "tiktoken",
  "confidence": "exact",
  "tokenizer_note": "Computed using exact tiktoken encoding 'o200k_base' with OpenAI chat markup overhead."
}
```

### 2. Pre-flight Budget Check & Blocking
```bash
curl -s -X POST http://localhost:8000/v1/cost/check \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "anthropic",
    "model": "claude-3-opus",
    "prompt": "Perform comprehensive audit...",
    "expected_output_tokens": 4000,
    "user_id": "team_finance",
    "reserve": true
  }'
```

---

## Local Setup

### Prerequisites
- Python 3.10+
- PostgreSQL 14+ (or SQLite for quick local experimentation)

### Installation
```bash
# 1. Clone the repository
git clone https://github.com/jemade/llm-cost-guard.git
cd llm-cost-guard

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements-dev.txt

# 4. Configure environment
cp .env.example .env

# 5. Run database migrations
alembic upgrade head

# 6. Seed sample development data (optional)
python -m app.cli.seed

# 7. Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000/dashboard` in your browser.

---

## Docker

Bring up the complete production-like environment with PostgreSQL in one command:

```bash
docker compose up --build
```

- API & Dashboard: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

---

## Testing

The test suite covers token estimation, pricing lookups, budget enforcement, edge cases ($0 budget, exact matches), concurrency reservations, and API routes:

```bash
pytest -v --tb=short
```

To run linting and type checking:
```bash
ruff check .
mypy app
```

---

## Deployment

### Recommended Platforms
- **AWS ECS / EKS** or **GCP Cloud Run** for the API container.
- **AWS RDS PostgreSQL** or **GCP Cloud SQL** for database storage.

### Environment Variables
| Variable | Description | Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | Async connection string (`postgresql+asyncpg://...`) | Required |
| `PRICING_FILE_PATH` | Path to `pricing.yaml` | `config/pricing.yaml` |
| `DEFAULT_DAILY_BUDGET` | Default daily limit in USD | `10.0` |
| `DEFAULT_WEEKLY_BUDGET` | Default weekly limit in USD | `50.0` |
| `DEFAULT_MONTHLY_BUDGET` | Default monthly limit in USD | `200.0` |
| `ALERT_WEBHOOK_URL` | Optional Slack/Discord webhook URL | `None` |
| `RESERVATION_TTL_SECONDS` | In-flight budget reservation TTL | `60` |

---

## Limitations

1. **Non-OpenAI Tokenizer Approximations**: Anthropic and Google use proprietary tokenizers that are not packaged as open-source offline Python libraries. While calibrations are empirical and close (~5-8% margin of error), exact token counts require the provider's remote API.
2. **Streaming Output Uncertainty**: Pre-flight cost estimation requires an `expected_output_tokens` assumption (or the model's `max_tokens`). Actual output length varies by response.
3. **Single-Cluster Locking**: Concurrency safety uses PostgreSQL row-level locks and reservations. In multi-region active-active deployments, a distributed lock manager (e.g. Redis Redlock) would be necessary.

---

## Future Improvements

- **Adaptive Output Prediction**: Machine learning or historical average heuristics to predict output token length by prompt type.
- **Provider Fallback Routing**: Automatically suggest or re-route blocked requests to cheaper equivalent models (e.g. Claude 3.5 Sonnet -> Haiku or GPT-4o -> GPT-4o-mini).
- **Prompt Caching Discounts**: Support for OpenAI and Anthropic prompt caching discount rates.

---

## Engineering Decisions

1. **Why Async SQLAlchemy 2.0?** FastAPI is asynchronous. Using async database drivers (`asyncpg`, `aiosqlite`) ensures request threads are not blocked during database operations, maintaining high throughput under concurrent load.
2. **Why Pessimistic Locking & Reservations?** Optimistic locking fails in high-concurrency environments because requests fail after the fact. Pre-flight reservations ensure that budget is reserved before the slow LLM call begins.
3. **Why Decimal for Cost?** Floating-point arithmetic introduces rounding artifacts (e.g. `0.1 + 0.2 = 0.30000000000000004`). In financial accounting, micro-dollar costs must be exact.

---

## Cost-Saving Demonstration

Run the reproducible demonstration:
```bash
python examples/budget_control_demo.py
```
See [`docs/demo.md`](docs/demo.md) for full scenario walkthrough.
