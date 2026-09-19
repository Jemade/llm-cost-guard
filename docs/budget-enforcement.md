# Budget Enforcement & Alerting Mechanics

## 1. Budget Scopes & Periods

LLM Cost Guard enforces budget limits across three distinct rolling calendar windows, strictly evaluated in UTC:

- **Daily**: Starts at `00:00:00 UTC` of the current calendar day.
- **Weekly**: Starts at `00:00:00 UTC` on Monday of the current week.
- **Monthly**: Starts at `00:00:00 UTC` on the 1st of the current month.

### Scope Hierarchy

Budgets can be configured at multiple granularity levels:
1. **User / Client Scope** (`user:{user_id}`): Dedicated budget for an individual developer, team, or microservice.
2. **Global Scope** (`global`): Fallback system-wide safety ceiling applied if no user-specific budget exists.

---

## 2. Spend Calculation Formula

For any target scope and period start time $T_{\text{start}}$:

$$\text{Spend} = \sum \text{UsageCost} + \sum \text{ActiveReservations}$$

Where:
- $\text{UsageCost} = \text{COALESCE}(\text{actual\_cost}, \text{estimated\_cost})$ for all records in `llm_usage_logs` where `timestamp` $\ge T_{\text{start}}$ and `status` $\ne \text{'BLOCKED'}$.
- $\text{ActiveReservations} = \text{estimated\_cost}$ for all records in `budget_reservations` where `status` = 'PENDING', `expires_at` $> \text{now()}$, and `created_at` $\ge T_{\text{start}}$.

---

## 3. Decision Matrix

When a pre-flight check arrives (`POST /v1/cost/check`):

| Condition | Decision | Reason Code |
| :--- | :--- | :--- |
| Configured budget is \$0.00 | **BLOCK** | `ZERO_BUDGET_CONFIGURED` |
| $\text{Spent} + \text{EstimatedCost} > \text{DailyBudget}$ | **BLOCK** | `REQUEST_EXCEEDS_DAILY_BUDGET` |
| $\text{Spent} + \text{EstimatedCost} > \text{WeeklyBudget}$ | **BLOCK** | `REQUEST_EXCEEDS_WEEKLY_BUDGET` |
| $\text{Spent} + \text{EstimatedCost} > \text{MonthlyBudget}$ | **BLOCK** | `REQUEST_EXCEEDS_MONTHLY_BUDGET` |
| Within all period limits | **ALLOW** | `WITHIN_BUDGET` |
| Budget inactive (`is_active = false`) | **ALLOW** | `BUDGET_INACTIVE` |

---

## 4. Concurrency Protection & In-Flight Reservations

When `reserve=True` is passed to `/v1/cost/check`:
1. The budget check transaction places a row-level pessimistic lock (`SELECT ... FOR UPDATE`) on `budget_configs`.
2. If approved, a `budget_reservations` record is created with a configurable TTL (`RESERVATION_TTL_SECONDS=60`).
3. Subsequent requests arriving milliseconds later immediately factor in the reserved funds.
4. When the LLM provider call finishes:
   - Call `/v1/usage` with the returned `reservation_id`.
   - The reservation transitions to `COMMITTED` and actual token counts/costs are logged.
5. If the request fails or is aborted before calling `/v1/usage`:
   - The reservation automatically expires after 60 seconds, freeing the hold.

---

## 5. Threshold Alerting & Spam Prevention

Budgets support configurable percentage thresholds (default: `[0.80, 0.90, 1.00]`).

### Alert Deduplication

To prevent flooding alert channels on high-frequency APIs:
- Every alert event is recorded in the `alert_events` table with a composite database constraint:
  `UNIQUE(scope, period_type, period_start, threshold)`
- Before emitting an alert for a threshold (e.g. 80%), the system queries if an alert event already exists for that specific `(scope, period, period_start, threshold)` tuple.
- If it exists, the alert is suppressed.
- If it does not exist, the alert is created, committed, and dispatched to:
  1. **Console**: High-visibility structured ASCII box in application logs.
  2. **Webhook**: HTTP POST with JSON payload (Slack/Discord compatible) if `ALERT_WEBHOOK_URL` is configured.
