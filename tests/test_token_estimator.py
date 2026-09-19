from app.services.pricing_catalog import pricing_catalog
from app.services.token_estimator import token_estimator


def test_openai_exact_tiktoken_prompt():
    pricing = pricing_catalog.get("openai", "gpt-4o")
    prompt = "Hello, world! This is a test prompt for token estimation."
    tokens, tokenizer_type, confidence, note = token_estimator.estimate_input_tokens(
        pricing=pricing, prompt=prompt
    )
    assert tokens > 0
    assert tokenizer_type == "tiktoken"
    assert confidence == "exact"
    assert "o200k_base" in note


def test_openai_chat_messages_overhead():
    pricing = pricing_catalog.get("openai", "gpt-4o")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]
    tokens, tokenizer_type, confidence, _ = token_estimator.estimate_input_tokens(
        pricing=pricing, messages=messages
    )
    # ChatML adds ~3 tokens per message + 3 priming tokens
    assert tokens >= 15
    assert confidence == "exact"


def test_anthropic_calibrated_approximation():
    pricing = pricing_catalog.get("anthropic", "claude-3-5-sonnet")
    prompt = "Analyze the performance characteristics of distributed key-value stores."
    tokens, tokenizer_type, confidence, note = token_estimator.estimate_input_tokens(
        pricing=pricing, prompt=prompt
    )
    assert tokens > 0
    assert tokenizer_type == "approximation"
    assert confidence == "approximation"
    assert "proprietary BPE" in note


def test_google_gemini_heuristic():
    pricing = pricing_catalog.get("google", "gemini-1.5-flash")
    prompt = "Explain photosynthesis in simple terms for elementary students."
    tokens, tokenizer_type, confidence, note = token_estimator.estimate_input_tokens(
        pricing=pricing, prompt=prompt
    )
    assert tokens > 0
    assert tokenizer_type == "approximation"
    assert confidence == "approximation"
    assert "SentencePiece" in note


def test_deepseek_approximation():
    pricing = pricing_catalog.get("deepseek", "deepseek-chat")
    prompt = "Implement a binary search algorithm in Python."
    tokens, tokenizer_type, confidence, _ = token_estimator.estimate_input_tokens(
        pricing=pricing, prompt=prompt
    )
    assert tokens > 0
    assert confidence == "approximation"


def test_empty_input_returns_zero():
    pricing = pricing_catalog.get("openai", "gpt-4o")
    tokens, _, _, _ = token_estimator.estimate_input_tokens(
        pricing=pricing, prompt="", messages=[]
    )
    assert tokens == 0
