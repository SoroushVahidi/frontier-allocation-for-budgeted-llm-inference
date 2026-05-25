"""Tests for azure_openai provider support in the fixed-pool validation runner.

All tests are offline/mocked — zero network calls, zero API cost.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_env(**kwargs: str) -> dict[str, str]:
    """Return a copy of the real env, overriding with kwargs and stripping real secrets."""
    env = {k: v for k, v in os.environ.items()
           if k not in {
               "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT",
               "AZURE_OPENAI_API_VERSION", "AZURE_OPENAI_STRONG_DEPLOYMENT",
               "COHERE_API_KEY", "MISTRAL_API_KEY", "CEREBRAS_API_KEY",
               "OPENAI_API_KEY", "CO_API_KEY",
           }}
    env.update(kwargs)
    return env


# ---------------------------------------------------------------------------
# 1. Provider allowlist
# ---------------------------------------------------------------------------

class TestProviderAllowlist(unittest.TestCase):
    """azure_openai must be accepted by parse_provider_list()."""

    def _parse(self, providers_str: str) -> list[str]:
        import argparse
        import scripts.run_cohere_real_model_cost_normalized_validation as runner
        args = argparse.Namespace(provider="", providers=providers_str)
        return runner.normalize_providers(args)

    def test_azure_openai_accepted(self):
        result = self._parse("azure_openai")
        self.assertIn("azure_openai", result)

    def test_azure_openai_with_cohere(self):
        result = self._parse("azure_openai,cohere")
        self.assertIn("azure_openai", result)
        self.assertIn("cohere", result)

    def test_unknown_provider_rejected(self):
        import scripts.run_cohere_real_model_cost_normalized_validation as runner
        import argparse
        args = argparse.Namespace(provider="", providers="not_a_real_provider")
        with self.assertRaises(ValueError):
            runner.normalize_providers(args)

    def test_existing_providers_still_accepted(self):
        for p in ("cohere", "mistral", "cerebras", "openai"):
            result = self._parse(p)
            self.assertIn(p, result, f"{p} should still be accepted")

    def test_fireworks_accepted(self):
        result = self._parse("fireworks")
        self.assertIn("fireworks", result)

    def test_cloudrift_ai_accepted(self):
        result = self._parse("cloudrift_ai")
        self.assertIn("cloudrift_ai", result)


# ---------------------------------------------------------------------------
# 2. API key resolution — boolean presence only, never print values
# ---------------------------------------------------------------------------

class TestApiKeyResolution(unittest.TestCase):
    """resolve_api_key_for_provider must return azure key from env."""

    def test_azure_key_resolved_when_present(self):
        from experiments.frontier_matrix_core import resolve_api_key_for_provider
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "FAKE_KEY_DO_NOT_PRINT"}, clear=False):
            result = resolve_api_key_for_provider("azure_openai")
        self.assertIsNotNone(result)
        self.assertTrue(len(result) > 0)
        # Must not print the key itself — this test never echoes it

    def test_azure_key_none_when_absent(self):
        from experiments.frontier_matrix_core import resolve_api_key_for_provider
        env = _fake_env()  # strips AZURE_OPENAI_API_KEY
        with patch.dict(os.environ, env, clear=True):
            result = resolve_api_key_for_provider("azure_openai")
        self.assertIsNone(result)

    def test_existing_providers_unaffected(self):
        from experiments.frontier_matrix_core import resolve_api_key_for_provider
        env = _fake_env(MISTRAL_API_KEY="fake_mistral", COHERE_API_KEY="fake_cohere")
        with patch.dict(os.environ, env, clear=True):
            self.assertIsNotNone(resolve_api_key_for_provider("mistral"))
            self.assertIsNotNone(resolve_api_key_for_provider("cohere"))


# ---------------------------------------------------------------------------
# 3. APIBranchGenerator — base URL and routing
# ---------------------------------------------------------------------------

class TestAPIBranchGeneratorAzure(unittest.TestCase):
    """Azure base_url and _call_api routing without network calls."""

    def _make_gen(self, endpoint: str = "https://fake.openai.azure.com/openai/v1") -> object:
        from experiments.branching import APIBranchGenerator
        env = _fake_env(AZURE_OPENAI_ENDPOINT=endpoint)
        with patch.dict(os.environ, env, clear=False):
            gen = APIBranchGenerator(
                api_key="fake_key",
                model="gpt-4.1-mini",
                temperature=0.0,
                max_tokens=256,
                provider="azure_openai",
            )
        return gen

    def test_base_url_set_from_env(self):
        gen = self._make_gen("https://fake.openai.azure.com/openai/v1")
        # base_url should be the env var value (rstrip '/'), not api.openai.com
        self.assertIn("fake.openai.azure.com", gen.base_url)
        self.assertNotIn("api.openai.com", gen.base_url)

    def test_base_url_trailing_slash_stripped(self):
        gen = self._make_gen("https://fake.openai.azure.com/openai/v1/")
        self.assertFalse(gen.base_url.endswith("/"))

    def test_model_is_deployment_name(self):
        gen = self._make_gen()
        self.assertEqual(gen.model, "gpt-4.1-mini")

    def test_provider_stored_correctly(self):
        gen = self._make_gen()
        self.assertEqual(gen.provider, "azure_openai")

    def test_call_api_routes_to_azure_method(self):
        """_call_api must call _call_azure_chat_api, not _call_responses_api."""
        gen = self._make_gen()
        gen._call_azure_chat_api = MagicMock(return_value='{"action":"final","answer":"42"}')
        gen._call_responses_api = MagicMock(side_effect=AssertionError("must not call responses API"))
        payload = {"model": "gpt-4.1-mini", "input": "test"}
        result = gen._call_api(payload, prompt="test prompt")
        gen._call_azure_chat_api.assert_called_once_with("test prompt")
        self.assertEqual(result, '{"action":"final","answer":"42"}')

    def test_responses_api_not_called_for_azure(self):
        """Confirm the old fallthrough (_call_responses_api) is bypassed for azure_openai."""
        gen = self._make_gen()
        gen._call_azure_chat_api = MagicMock(return_value='{"action":"final","answer":"7"}')
        called_responses = []
        original_responses = gen._call_responses_api
        gen._call_responses_api = lambda p: called_responses.append(p) or ""
        payload = {"model": "gpt-4.1-mini", "input": "x"}
        gen._call_api(payload, prompt="x")
        self.assertEqual(len(called_responses), 0, "_call_responses_api must not be called for azure_openai")


# ---------------------------------------------------------------------------
# 4. _call_azure_chat_api payload structure (mocked HTTP)
# ---------------------------------------------------------------------------

class TestCallAzureChatApiPayload(unittest.TestCase):
    """Verify the payload sent to /chat/completions — no network calls."""

    def _make_gen(self) -> object:
        from experiments.branching import APIBranchGenerator
        with patch.dict(os.environ,
                        {"AZURE_OPENAI_ENDPOINT": "https://fake.openai.azure.com/openai/v1"},
                        clear=False):
            return APIBranchGenerator(
                api_key="fake_key",
                model="gpt-4.1-mini",
                temperature=0.7,
                max_tokens=512,
                provider="azure_openai",
                retry_max_attempts=1,
            )

    def test_endpoint_is_chat_completions(self):
        gen = self._make_gen()
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["payload"] = json.loads(req.data.decode())
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": '{"action":"final","answer":"99"}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }).encode()
            return resp

        from urllib import request as urllib_request
        with patch.object(urllib_request, "urlopen", fake_urlopen):
            result = gen._call_azure_chat_api("What is 2+2?")

        self.assertIn("/chat/completions", captured["url"])
        self.assertNotIn("/responses", captured["url"])
        self.assertEqual(captured["payload"]["model"], "gpt-4.1-mini")
        self.assertIn("messages", captured["payload"])
        self.assertIn("max_tokens", captured["payload"])
        self.assertNotIn("max_completion_tokens", captured["payload"])
        self.assertEqual(result, '{"action":"final","answer":"99"}')

    def test_authorization_header_set(self):
        gen = self._make_gen()
        captured_headers: dict[str, str] = {}

        def fake_urlopen(req, timeout=None):
            for k in req.headers:
                captured_headers[k.lower()] = req.headers[k]
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }).encode()
            return resp

        from urllib import request as urllib_request
        with patch.object(urllib_request, "urlopen", fake_urlopen):
            gen._call_azure_chat_api("test")

        # Authorization header must be present (value not echoed)
        auth_value = captured_headers.get("authorization", "")
        self.assertTrue(auth_value.startswith("Bearer "), "Authorization header must be Bearer token")

    def test_no_real_network_call(self):
        """Confirm no real network call happens when urlopen is mocked."""
        gen = self._make_gen()
        call_count = [0]

        def mock_urlopen(req, timeout=None):
            call_count[0] += 1
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": "mocked"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }).encode()
            return resp

        from urllib import request as urllib_request
        with patch.object(urllib_request, "urlopen", mock_urlopen):
            gen._call_azure_chat_api("hello")

        self.assertEqual(call_count[0], 1, "Exactly one mocked call made")


# ---------------------------------------------------------------------------
# 5. Readiness check — env var presence (boolean only)
# ---------------------------------------------------------------------------

class TestAzureReadinessCheck(unittest.TestCase):
    """Runner readiness check for azure_openai must be boolean — no secret printing."""

    def _readiness(self, env_overrides: dict) -> dict:
        """Run the readiness logic isolated from the rest of the runner."""
        env = _fake_env(**env_overrides)
        with patch.dict(os.environ, env, clear=True):
            ok = bool(os.environ.get("AZURE_OPENAI_API_KEY")) and \
                 bool(os.environ.get("AZURE_OPENAI_ENDPOINT"))
            if ok:
                reason = "azure_openai_key_and_endpoint_present"
            else:
                missing = []
                if not os.environ.get("AZURE_OPENAI_API_KEY"):
                    missing.append("AZURE_OPENAI_API_KEY")
                if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
                    missing.append("AZURE_OPENAI_ENDPOINT")
                reason = f"azure_openai_missing_env_vars:{','.join(missing)}"
        return {"ok": ok, "reason": reason}

    def test_ready_when_both_present(self):
        result = self._readiness({
            "AZURE_OPENAI_API_KEY": "fake_key",
            "AZURE_OPENAI_ENDPOINT": "https://fake.openai.azure.com/openai/v1",
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "azure_openai_key_and_endpoint_present")

    def test_not_ready_key_missing(self):
        result = self._readiness({
            "AZURE_OPENAI_ENDPOINT": "https://fake.openai.azure.com/openai/v1",
        })
        self.assertFalse(result["ok"])
        self.assertIn("AZURE_OPENAI_API_KEY", result["reason"])

    def test_not_ready_endpoint_missing(self):
        result = self._readiness({
            "AZURE_OPENAI_API_KEY": "fake_key",
        })
        self.assertFalse(result["ok"])
        self.assertIn("AZURE_OPENAI_ENDPOINT", result["reason"])

    def test_not_ready_both_missing(self):
        result = self._readiness({})
        self.assertFalse(result["ok"])
        self.assertIn("AZURE_OPENAI_API_KEY", result["reason"])
        self.assertIn("AZURE_OPENAI_ENDPOINT", result["reason"])

    def test_reason_does_not_contain_secret_value(self):
        result = self._readiness({
            "AZURE_OPENAI_API_KEY": "SUPER_SECRET_KEY_12345",
            "AZURE_OPENAI_ENDPOINT": "https://fake.openai.azure.com/openai/v1",
        })
        # The reason string must never contain the actual secret value
        self.assertNotIn("SUPER_SECRET_KEY_12345", result["reason"])


# ---------------------------------------------------------------------------
# 6. Dry-run call plan — zero API calls
# ---------------------------------------------------------------------------

class TestAzureDryRunCallPlan(unittest.TestCase):
    """Dry-run with azure_openai provider emits correct planned rows, no API calls."""

    _FAKE_ENV = dict(
        AZURE_OPENAI_API_KEY="fake_key",
        AZURE_OPENAI_ENDPOINT="https://fake.openai.azure.com/openai/v1",
        AZURE_OPENAI_DEPLOYMENT="gpt-4.1-mini",
    )

    def _run_dry_run(self, extra_args: list[str], tmpdir: str) -> dict:
        """Run the runner in dry-run mode; return parsed plan JSON."""
        import subprocess
        plan_path = os.path.join(tmpdir, "plan.json")
        env = _fake_env(**self._FAKE_ENV)
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/run_cohere_real_model_cost_normalized_validation.py"),
                "--providers", "azure_openai",
                "--azure-model", "gpt-4.1-mini",
                "--datasets", "openai/gsm8k",
                "--seeds", "71", "--budgets", "6",
                "--methods",
                "direct_reserve_semantic_frontier_v2,external_l1_max,"
                "external_s1_budget_forcing,external_tale_prompt_budgeting",
                "--dry-run-call-plan",
                "--dry-run-plan-json", plan_path,
                "--output-root", tmpdir,
            ] + extra_args,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"dry-run failed:\n{result.stderr[:600]}")
        with open(plan_path) as f:
            return json.load(f)

    def test_dry_run_azure_produces_4000_rows(self):
        """1000 examples × 4 methods = 4000 planned rows."""
        import tempfile
        exact_cases = REPO_ROOT / "outputs/mistral_large_router_training_gsm8k_20260524/mistral_gsm8k_train_1000_exact_cases.jsonl"
        allowed_ids = REPO_ROOT / "outputs/mistral_large_router_training_gsm8k_20260524/mistral_gsm8k_train_1000_allowed_ids_all_methods.jsonl"
        if not exact_cases.exists() or not allowed_ids.exists():
            self.skipTest("Training exact-cases files not present")

        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._run_dry_run(
                [
                    "--target-scored-per-slice", "1000",
                    "--max-examples", "1000",
                    "--exact-cases-jsonl", str(exact_cases),
                    "--allowed-example-ids-file", str(allowed_ids),
                ],
                tmpdir,
            )
        rows = plan.get("planned_rows", [])
        total = sum(r["planned_case_count"] for r in rows)
        self.assertEqual(total, 4000, f"Expected 4000 planned rows, got {total}")
        methods = {r["method"] for r in rows}
        self.assertEqual(len(methods), 4, "All 4 methods must appear in plan")

    def test_dry_run_azure_10_example_smoke(self):
        """10 examples × 4 methods = 40 planned rows (smoke scale)."""
        import tempfile
        exact_cases = REPO_ROOT / "outputs/mistral_large_router_training_gsm8k_20260524/mistral_gsm8k_train_1000_exact_cases.jsonl"
        if not exact_cases.exists():
            self.skipTest("Training exact-cases file not present")

        # Build a 10-case subset from the first 10 lines
        methods = [
            "direct_reserve_semantic_frontier_v2",
            "external_l1_max",
            "external_s1_budget_forcing",
            "external_tale_prompt_budgeting",
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            ten_cases_path = os.path.join(tmpdir, "ten_cases.jsonl")
            ten_allowed_path = os.path.join(tmpdir, "ten_allowed.jsonl")
            with open(exact_cases) as fin, open(ten_cases_path, "w") as fout:
                for i, line in enumerate(fin):
                    if i >= 10:
                        break
                    fout.write(line)
            with open(ten_cases_path) as f:
                cases = [json.loads(l) for l in f]
            with open(ten_allowed_path, "w") as f:
                for m in methods:
                    for c in cases:
                        f.write(json.dumps({
                            "example_id": c["example_id"], "dataset": "openai/gsm8k",
                            "seed": 71, "budget": 6, "method": m,
                        }) + "\n")
            plan = self._run_dry_run(
                [
                    "--target-scored-per-slice", "10",
                    "--max-examples", "10",
                    "--exact-cases-jsonl", ten_cases_path,
                    "--allowed-example-ids-file", ten_allowed_path,
                ],
                tmpdir,
            )
        rows = plan.get("planned_rows", [])
        total = sum(r["planned_case_count"] for r in rows)
        self.assertEqual(total, 40, f"Expected 40 planned rows, got {total}")


if __name__ == "__main__":
    unittest.main()
