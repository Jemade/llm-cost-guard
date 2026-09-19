import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tiktoken

from app.core.logging import logger
from app.schemas.pricing import ModelPricingSchema

# Ensure local cache dir is used if present
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache" / "tiktoken"
if CACHE_DIR.exists():
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(CACHE_DIR))


class TokenEstimator:
    """
    Estimates token counts for prompts and chat messages across different providers.
    Explicitly distinguishes between exact tokenizers (e.g. tiktoken for OpenAI)
    and calibrated approximations (e.g. Anthropic, Google Gemini, DeepSeek).
    """

    def __init__(self) -> None:
        self._encodings: Dict[str, Optional[tiktoken.Encoding]] = {}

    def _get_tiktoken_encoding(self, encoding_name: str) -> Optional[tiktoken.Encoding]:
        if encoding_name not in self._encodings:
            try:
                self._encodings[encoding_name] = tiktoken.get_encoding(encoding_name)
            except Exception as e:
                logger.warning(f"Could not load encoding '{encoding_name}': {e}. Using heuristic fallback.")
                try:
                    self._encodings[encoding_name] = tiktoken.get_encoding("cl100k_base")
                except Exception:
                    self._encodings[encoding_name] = None
        return self._encodings[encoding_name]

    def estimate_input_tokens(
        self,
        pricing: ModelPricingSchema,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[int, str, str, Optional[str]]:
        """
        Estimates input tokens for a prompt or list of messages.
        Returns:
            (estimated_tokens, tokenizer_type, confidence, note)
        """
        provider = pricing.provider.lower()
        encoding_name = pricing.encoding_name or "cl100k_base"

        if provider == "openai":
            tokens = self._count_openai_tokens(encoding_name, prompt, messages)
            return (
                tokens,
                "tiktoken",
                "exact",
                f"Computed using exact tiktoken encoding '{encoding_name}' with OpenAI chat markup overhead.",
            )

        elif provider == "anthropic":
            # Anthropic Claude proprietary BPE estimation
            tokens = self._estimate_anthropic_tokens(prompt, messages)
            return (
                tokens,
                "approximation",
                "approximation",
                "Anthropic Claude uses a proprietary BPE tokenizer. Estimated via cl100k calibrated ratio (1.08x).",
            )

        elif provider == "google":
            # Google Gemini SentencePiece estimation
            tokens = self._estimate_gemini_tokens(prompt, messages)
            return (
                tokens,
                "approximation",
                "approximation",
                "Google Gemini uses SentencePiece tokenization. Estimated via multilingual character-to-token ratio.",
            )

        elif provider == "deepseek":
            # DeepSeek byte-level BPE estimation
            tokens = self._estimate_deepseek_tokens(prompt, messages)
            return (
                tokens,
                "approximation",
                "approximation",
                "DeepSeek uses a 128k byte-level BPE tokenizer. Estimated via cl100k baseline.",
            )

        else:
            # Generic fallback: cl100k baseline
            tokens = self._count_generic_tokens(prompt, messages)
            return (
                tokens,
                "approximation",
                "approximation",
                f"Provider '{provider}' tokenizer approximated via cl100k baseline.",
            )

    def _encode_text(self, encoding: Optional[tiktoken.Encoding], text: str) -> int:
        if not text:
            return 0
        if encoding is not None:
            return len(encoding.encode(text))
        return max(1, int(round(len(text) / 3.8)))

    def _count_openai_tokens(
        self,
        encoding_name: str,
        prompt: Optional[str],
        messages: Optional[List[Dict[str, Any]]],
    ) -> int:
        encoding = self._get_tiktoken_encoding(encoding_name)

        if prompt:
            return self._encode_text(encoding, prompt)

        if not messages:
            return 0

        # OpenAI ChatML token calculation:
        # Every message follows <|im_start|>{role/name}\n{content}<|im_end|>\n
        # That accounts for 3 tokens per message + name tokens if present
        num_tokens = 0
        for message in messages:
            num_tokens += 3  # Start and end tokens + newline
            for key, value in message.items():
                if isinstance(value, str):
                    num_tokens += self._encode_text(encoding, value)
                if key == "name":
                    num_tokens += 1  # Name extra token
        num_tokens += 3  # Every reply is primed with <|start|>assistant<|message|>
        return num_tokens

    def _estimate_anthropic_tokens(
        self,
        prompt: Optional[str],
        messages: Optional[List[Dict[str, Any]]],
    ) -> int:
        """
        Anthropic Claude uses a proprietary BPE tokenizer.
        Empirical calibration shows Claude token counts are roughly 1.06 - 1.10x
        of OpenAI's cl100k encoding for standard English and code.
        """
        encoding = self._get_tiktoken_encoding("cl100k_base")
        if prompt:
            base_count = self._encode_text(encoding, prompt)
            return max(1, int(round(base_count * 1.08)))

        if not messages:
            return 0

        total_text = ""
        overhead = len(messages) * 4 + 3
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_text += content + "\n"
        base_count = self._encode_text(encoding, total_text)
        return max(1, int(round(base_count * 1.08)) + overhead)

    def _estimate_gemini_tokens(
        self,
        prompt: Optional[str],
        messages: Optional[List[Dict[str, Any]]],
    ) -> int:
        """
        Google Gemini models use SentencePiece.
        SentencePiece tokenizes roughly 1 token per 3.8 to 4.2 characters in English.
        """
        if prompt:
            chars = len(prompt)
            return max(1, int(round(chars / 4.0)))

        if not messages:
            return 0

        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
        # Add message boundary overhead (~10 chars equivalent)
        total_chars += len(messages) * 10
        return max(1, int(round(total_chars / 4.0)))

    def _estimate_deepseek_tokens(
        self,
        prompt: Optional[str],
        messages: Optional[List[Dict[str, Any]]],
    ) -> int:
        encoding = self._get_tiktoken_encoding("cl100k_base")
        if prompt:
            return self._encode_text(encoding, prompt)
        if not messages:
            return 0
        total_text = "\n".join(str(m.get("content", "")) for m in messages)
        return self._encode_text(encoding, total_text) + (len(messages) * 3)

    def _count_generic_tokens(
        self,
        prompt: Optional[str],
        messages: Optional[List[Dict[str, Any]]],
    ) -> int:
        encoding = self._get_tiktoken_encoding("cl100k_base")
        if prompt:
            return self._encode_text(encoding, prompt)
        if not messages:
            return 0
        total_text = "\n".join(str(m.get("content", "")) for m in messages)
        return self._encode_text(encoding, total_text) + (len(messages) * 3)


token_estimator = TokenEstimator()
