"""Tests for Cloudrift/Qwen3 thinking-mode suppression in APIBranchGenerator.

Verifies that:
- Cloudrift + Qwen model adds chat_template_kwargs: {enable_thinking: False}
- Cloudrift + non-Qwen model does NOT add extra keys
- Fireworks (other OpenAI-compatible) does not receive Cloudrift-specific keys
- Cohere/Mistral/Azure/OpenAI providers are not affected
- Both 'cloudrift' and 'cloudrift_ai' aliases are covered
- Model name matching is case-insensitive
"""

import pytest
from experiments.branching import APIBranchGenerator


# ─── _cloudrift_extra_payload unit tests ─────────────────────────────────────

class TestCloudriftExtraPayload:

    def test_cloudrift_qwen_model_adds_disable_thinking(self):
        result = APIBranchGenerator._cloudrift_extra_payload("cloudrift", "Qwen/Qwen3.6-35B-A3B-FP8")
        assert result == {"chat_template_kwargs": {"enable_thinking": False}}

    def test_cloudrift_ai_qwen_model_adds_disable_thinking(self):
        result = APIBranchGenerator._cloudrift_extra_payload("cloudrift_ai", "Qwen/Qwen3-32B")
        assert result == {"chat_template_kwargs": {"enable_thinking": False}}

    def test_qwen_model_name_case_insensitive(self):
        # Model names from APIs can have varied capitalisation
        assert APIBranchGenerator._cloudrift_extra_payload("cloudrift", "qwen3-32b") == \
               {"chat_template_kwargs": {"enable_thinking": False}}
        assert APIBranchGenerator._cloudrift_extra_payload("cloudrift", "QWEN/QWEN3-72B") == \
               {"chat_template_kwargs": {"enable_thinking": False}}

    def test_cloudrift_non_qwen_model_returns_empty(self):
        result = APIBranchGenerator._cloudrift_extra_payload("cloudrift", "llama-3.1-70b")
        assert result == {}

    def test_cloudrift_ai_non_qwen_model_returns_empty(self):
        result = APIBranchGenerator._cloudrift_extra_payload("cloudrift_ai", "mistral-7b")
        assert result == {}

    def test_fireworks_qwen_model_returns_empty(self):
        # Fireworks is also OpenAI-compatible but must not receive Cloudrift-specific keys
        result = APIBranchGenerator._cloudrift_extra_payload("fireworks", "Qwen/Qwen3-32B")
        assert result == {}

    def test_cohere_not_affected(self):
        assert APIBranchGenerator._cloudrift_extra_payload("cohere", "command-r-plus") == {}

    def test_mistral_not_affected(self):
        assert APIBranchGenerator._cloudrift_extra_payload("mistral", "mistral-large-latest") == {}

    def test_azure_openai_not_affected(self):
        assert APIBranchGenerator._cloudrift_extra_payload("azure_openai", "gpt-4o") == {}

    def test_openai_not_affected(self):
        assert APIBranchGenerator._cloudrift_extra_payload("openai", "gpt-4o") == {}

    def test_cerebras_not_affected(self):
        assert APIBranchGenerator._cloudrift_extra_payload("cerebras", "llama-3.1-70b") == {}

    def test_empty_model_string_returns_empty(self):
        # Guard against edge case of empty/None-ish model name
        assert APIBranchGenerator._cloudrift_extra_payload("cloudrift", "") == {}

    def test_enable_thinking_value_is_false_not_falsy(self):
        result = APIBranchGenerator._cloudrift_extra_payload("cloudrift", "Qwen/Qwen3-32B")
        assert result["chat_template_kwargs"]["enable_thinking"] is False


# ─── Payload integration: ensure keys appear in actual payload dict ───────────

class TestPayloadIntegration:
    """Confirm the extra keys are merged into the constructed payload."""

    def _make_generator(self, provider: str, model: str) -> APIBranchGenerator:
        return APIBranchGenerator(
            api_key="test_key",
            model=model,
            temperature=0.0,
            max_tokens=64,
            provider=provider,
        )

    def test_cloudrift_qwen_payload_contains_extra_key(self):
        gen = self._make_generator("cloudrift", "Qwen/Qwen3.6-35B-A3B-FP8")
        extra = APIBranchGenerator._cloudrift_extra_payload(gen.provider, gen.model)
        assert "chat_template_kwargs" in extra
        assert extra["chat_template_kwargs"]["enable_thinking"] is False

    def test_cloudrift_ai_qwen_payload_contains_extra_key(self):
        gen = self._make_generator("cloudrift_ai", "Qwen/Qwen3-32B")
        extra = APIBranchGenerator._cloudrift_extra_payload(gen.provider, gen.model)
        assert "chat_template_kwargs" in extra

    def test_fireworks_qwen_payload_does_not_contain_extra_key(self):
        gen = self._make_generator("fireworks", "Qwen/Qwen3-32B")
        extra = APIBranchGenerator._cloudrift_extra_payload(gen.provider, gen.model)
        assert "chat_template_kwargs" not in extra

    def test_cohere_payload_does_not_contain_extra_key(self):
        gen = self._make_generator("cohere", "command-r-plus")
        extra = APIBranchGenerator._cloudrift_extra_payload(gen.provider, gen.model)
        assert extra == {}
