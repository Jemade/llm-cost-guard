# Cost-Saving & Budget Blocking Demonstration

This walkthrough documents a controlled, reproducible scenario demonstrating how LLM Cost Guard prevents financial overruns before provider requests are dispatched.

---

## 1. Scenario Parameters

- **User**: `user:demo_client`
- **Daily Budget**: \$10.00
- **Simulated Existing Spend Today**: \$9.70
- **Remaining Daily Budget**: **\$0.30**

---

## 2. Execution Walkthrough

### Step 1: Attempting an Expensive Model Call (Claude 3 Opus)

The client plans a heavy architectural analysis task:
- **Provider**: `anthropic`
- **Model**: `claude-3-opus` (\$15.00 / 1M input, \$75.00 / 1M output)
- **Input Tokens**: ~10,000 tokens
- **Expected Output Tokens**: 3,600 tokens

**Pre-flight Cost Calculation**:
$$\text{Cost} = \left(\frac{10,000}{1,000,000} \times \$15.00\right) + \left(\frac{3,600}{1,000,000} \times \$75.00\right) = \$0.1500 + \$0.2700 = \$0.4200$$

**Budget Evaluation**:
$$\text{Spent Today (\$9.70)} + \text{Estimated Request (\$0.42)} = \$10.12 > \$10.00 \text{ Limit}$$

**Outcome**:
- **Decision**: `BLOCK`
- **Reason**: `REQUEST_EXCEEDS_DAILY_BUDGET`
- **Action**: The system halts execution immediately. **No request is sent to the LLM provider, and zero API charges are incurred.**

---

### Step 2: Fallback to Cost-Optimized Alternative (GPT-4o Mini)

Recognizing the budget block, the client falls back to a cost-efficient model for the same task:
- **Provider**: `openai`
- **Model**: `gpt-4o-mini` (\$0.15 / 1M input, \$0.60 / 1M output)
- **Input Tokens**: ~9,259 tokens
- **Expected Output Tokens**: 3,600 tokens

**Pre-flight Cost Calculation**:
$$\text{Cost} = \left(\frac{9,259}{1,000,000} \times \$0.15\right) + \left(\frac{3,600}{1,000,000} \times \$0.60\right) = \$0.001389 + \$0.002160 = \$0.003549$$

**Budget Evaluation**:
$$\text{Spent Today (\$9.70)} + \text{Estimated Request (\$0.003549)} = \$9.703549 \le \$10.00 \text{ Limit}$$

**Outcome**:
- **Decision**: `ALLOW`
- **Reason**: `WITHIN_BUDGET`
- **Action**: Request proceeds, receives a temporary reservation ID, executes, and records actual usage.
- **Updated Remaining Budget**: \$0.2965

---

## 3. How to Reproduce

Run the automated demonstration script:

```bash
python examples/budget_control_demo.py
```

### Verified Terminal Output

```text
======================================================================
       LLM COST GUARD - BUDGET CONTROL & BLOCKING DEMO
======================================================================

[Step 1] Configuring daily budget for 'user:demo_client': $10.00
[Step 2] Simulating prior usage of $9.70 today...
         Current Daily Budget: $10.00
         Current Spent Today:  $9.7000
         Remaining Budget:     $0.3000

[Step 3] Pre-flight Check: Expensive Request (anthropic/claude-3-opus)
         Prompt Tokens:     10,000
         Expected Output:   3,600
         Estimated Cost:    $0.4200
         Remaining Budget:  $0.3000
⚠️  BUDGET ALERT: 80.0% THRESHOLD EXCEEDED (97.0%)
⚠️  BUDGET ALERT: 90.0% THRESHOLD EXCEEDED (97.0%)
         --> DECISION: BLOCK
         --> REASON:   REQUEST_EXCEEDS_DAILY_BUDGET
         🛡️  [PROTECTION ACTIVE] Request blocked before calling provider!

[Step 4] Fallback Attempt: Cost-Optimized Request (openai/gpt-4o-mini)
         Prompt Tokens:     9,259
         Expected Output:   3,600
         Estimated Cost:    $0.003549
         Remaining Budget:  $0.3000
         --> DECISION: ALLOW
         --> REASON:   WITHIN_BUDGET
         ✅ [APPROVED] Request fits within remaining budget.
         Reservation ID held: 1e7b07cf-e540-4229-835f-90c1c2154304

[Step 5] Final Status:
         New Daily Spent:     $9.7035 / $10.00
         New Remaining:       $0.2965
======================================================================
```
