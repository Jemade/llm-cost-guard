# LLM Pricing Catalog & Estimation Mechanics

## 1. Source of Truth

Model pricing is maintained in [`config/pricing.yaml`](../config/pricing.yaml). Prices are **never** hardcoded into Python application logic.

### Verified Model Pricing (as of February 2025)

| Provider | Model | Input Cost / 1M | Output Cost / 1M | Tokenizer | Effective Date | Last Verified |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **OpenAI** | `gpt-4o` | \$2.50 | \$10.00 | `tiktoken` (`o200k_base`) | 2024-08-06 | 2025-01-15 |
| **OpenAI** | `gpt-4o-mini` | \$0.15 | \$0.60 | `tiktoken` (`o200k_base`) | 2024-07-18 | 2025-01-15 |
| **OpenAI** | `o1` | \$15.00 | \$60.00 | `tiktoken` (`o200k_base`) | 2024-12-17 | 2025-01-15 |
| **OpenAI** | `o3-mini` | \$1.10 | \$4.40 | `tiktoken` (`o200k_base`) | 2025-01-31 | 2025-02-01 |
| **OpenAI** | `gpt-4-turbo` | \$10.00 | \$30.00 | `tiktoken` (`cl100k_base`) | 2024-04-09 | 2025-01-15 |
| **Anthropic** | `claude-3-5-sonnet` | \$3.00 | \$15.00 | Calibrated BPE (1.08x) | 2024-10-22 | 2025-01-15 |
| **Anthropic** | `claude-3-5-haiku` | \$0.80 | \$4.00 | Calibrated BPE (1.08x) | 2024-11-04 | 2025-01-15 |
| **Anthropic** | `claude-3-opus` | \$15.00 | \$75.00 | Calibrated BPE (1.08x) | 2024-02-29 | 2025-01-15 |
| **Google** | `gemini-1.5-pro` | \$1.25 | \$5.00 | SentencePiece heuristic | 2024-05-14 | 2025-01-15 |
| **Google** | `gemini-1.5-flash` | \$0.075 | \$0.30 | SentencePiece heuristic | 2024-05-14 | 2025-01-15 |
| **Google** | `gemini-2.0-flash` | \$0.10 | \$0.40 | SentencePiece heuristic | 2024-12-11 | 2025-01-15 |
| **DeepSeek** | `deepseek-chat` (V3) | \$0.14 | \$0.28 | Calibrated BPE | 2024-12-26 | 2025-01-15 |
| **DeepSeek** | `deepseek-reasoner` (R1) | \$0.55 | \$2.19 | Calibrated BPE | 2025-01-20 | 2025-01-25 |

---

## 2. Tokenizer Differences & Estimation Disclaimers

Tokenization algorithms differ fundamentally across providers:

1. **OpenAI (`tiktoken`)**:
   - `o200k_base`: Used by GPT-4o, o1, and o3-mini.
   - `cl100k_base`: Used by GPT-4 Turbo and GPT-3.5.
   - **Confidence**: `exact`. Token counts directly match the official OpenAI BPE vocabulary. Chat message framing overhead (~3 tokens per message + 3 priming tokens) is factored into calculations.

2. **Anthropic Claude**:
   - Claude models use a proprietary BPE tokenizer not published as an open-source local library.
   - **Confidence**: `approximation`. Calibrated against empirical Claude token distributions (~1.08x of `cl100k_base`).
   - Responses explicitly carry `confidence: "approximation"` and an explanatory note.

3. **Google Gemini**:
   - Gemini models use SentencePiece with a large multilingual vocabulary.
   - **Confidence**: `approximation`. Evaluated using a multilingual character-to-token heuristic (~4.0 characters per token in English).

---

## 3. How to Update Prices

To update model prices or add a new model:

1. Edit [`config/pricing.yaml`](../config/pricing.yaml):
   ```yaml
   - provider: "openai"
     model: "gpt-4.5-preview"
     input_cost_per_1m_tokens: 75.00
     output_cost_per_1m_tokens: 150.00
     effective_date: "2025-02-27"
     last_verified: "2025-02-27"
   ```
2. The pricing catalog reloads dynamically on application startup or via `pricing_catalog.reload()`. No application logic or code changes are required.

---

## 4. Handling Missing Models

If an application requests an estimation or cost check for a model not listed in `pricing.yaml`:
- The service raises `ModelPricingNotFoundError(provider, model)`.
- The API responds with `404 Not Found` and a clear error message:
  ```json
  {"detail": "No pricing configured for provider 'openai' and model 'gpt-5-unreleased'."}
  ```

---

## 5. Historical Usage Preservation

When provider pricing changes:
- `LLMUsageLog` stores `estimated_cost` and `actual_cost` as immutable snapshot values recorded at the moment the request executed.
- Past usage logs are **never** retroactively modified or recalculated when `pricing.yaml` is updated. This guarantees auditability and historical financial reporting accuracy.
