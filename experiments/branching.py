"""Branch state and branch operations for the lightweight pilot experiment."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import random
import re
import socket
import time
from typing import Any, Optional
from urllib import error, request

from experiments.code_sandbox import run_restricted_python
from experiments.data import ANSWER_PATTERN, extract_final_answer

_JSON_FENCE_FULL = re.compile(
    r"^\s*```(?:json|JSON)?\s*\r?\n?(.*)\r?\n?```\s*$",
    re.DOTALL,
)
_JSON_FENCE_EMBED = re.compile(r"```(?:json|JSON)?\s*\r?\n(.*?)```", re.DOTALL)
_FINAL_ANS_PHRASE_RE = re.compile(
    r"(?i)(?:final\s+answer|the\s+answer\s+is|answer\s+is)\s*[:=]?\s*([-+]?\d[\d,]*(?:\.\d+)?)",
)
_REASONING_NUMERIC_MINING_HINT = re.compile(
    r"(?i)\b(therefore|hence|in conclusion|overall|finally|total\s+is|answer\s+is|result\s+is)\b",
)
_NUMERIC_LEAF_LABEL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)provisional\s+answer\s*:\s*([-+]?\d[\d,]*(?:\.\d+)?)"), "provisional_answer"),
    (re.compile(r"(?i)numeric\s+leaf\s*:\s*([-+]?\d[\d,]*(?:\.\d+)?)"), "numeric_leaf"),
    (re.compile(r"(?i)computed\s+value\s*:\s*([-+]?\d[\d,]*(?:\.\d+)?)"), "computed_value"),
    (re.compile(r"(?i)therefore\s+the\s+answer\s+is\s*:\s*([-+]?\d[\d,]*(?:\.\d+)?)"), "therefore_answer"),
]


def extract_labeled_numeric_leaf_from_step(step_text: str) -> tuple[str, str]:
    """Gold-free: extract a numeric leaf only from explicit labels (no loose last-number mining)."""
    if not step_text or not str(step_text).strip():
        return "", ""
    t = str(step_text)
    for pat, tag in _NUMERIC_LEAF_LABEL_PATTERNS:
        m = pat.search(t)
        if m:
            return m.group(1).replace(",", ""), f"labeled_step_{tag}"
    return "", ""
_EXPAND_ANSWER_KEYS: tuple[str, ...] = (
    "answer",
    "final_answer",
    "numeric_answer",
    "solution_answer",
    "candidate_answer",
    "result",
)
_EXPAND_REASONING_TEXT_KEYS: tuple[str, ...] = (
    "step",
    "rationale_short",
    "reasoning",
    "chain_of_thought",
    "thought",
)
_VERIFY_ANSWER_KEYS: tuple[str, ...] = (
    "candidate_answer",
    "final_answer",
    "answer",
    "numeric_answer",
    "solution_answer",
    "result",
)

_LOGICAL_API_CALL_BUDGET: int | None = None
_LOGICAL_API_CALLS_CONSUMED: int = 0


def configure_logical_api_call_budget(max_calls: int | None) -> None:
    """Enable a global cap on logical API calls from ``APIBranchGenerator``.

    Each entry into ``APIBranchGenerator._call_api`` consumes one slot before any network I/O.
    Retries inside a single logical call do not consume extra slots.

    Pass ``None`` or non-positive values to disable (default). Safe for simulator-only runs.
    """
    global _LOGICAL_API_CALL_BUDGET, _LOGICAL_API_CALLS_CONSUMED
    _LOGICAL_API_CALL_BUDGET = max_calls if max_calls is not None and max_calls > 0 else None
    _LOGICAL_API_CALLS_CONSUMED = 0


def logical_api_call_budget_snapshot() -> dict[str, int | None]:
    return {"budget": _LOGICAL_API_CALL_BUDGET, "consumed": _LOGICAL_API_CALLS_CONSUMED}


def _consume_logical_api_call_budget() -> None:
    global _LOGICAL_API_CALLS_CONSUMED
    if _LOGICAL_API_CALL_BUDGET is None:
        return
    if _LOGICAL_API_CALLS_CONSUMED >= _LOGICAL_API_CALL_BUDGET:
        raise RuntimeError(
            "Global logical API call cap reached "
            f"({_LOGICAL_API_CALLS_CONSUMED} >= {_LOGICAL_API_CALL_BUDGET}). "
            "Increase --max-total-api-calls or reduce workload."
        )
    _LOGICAL_API_CALLS_CONSUMED += 1


@dataclass
class BranchState:
    """State for one partial reasoning trajectory."""

    branch_id: str
    latent_quality: float
    steps: list[str] = field(default_factory=list)
    score: float = 0.5
    predicted_answer: Optional[str] = None
    is_done: bool = False
    is_pruned: bool = False
    stalled_steps: int = 0
    recent_delta: float = 0.0
    verify_count: int = 0
    branch_age: int = 0
    action_history: list[str] = field(default_factory=list)
    score_history: list[float] = field(default_factory=list)
    depth_history: list[int] = field(default_factory=list)
    parent_branch_id: str | None = None
    trace_events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def depth(self) -> int:
        """Number of expansion steps already taken for this branch."""
        return len(self.steps)


@dataclass
class BranchActionResult:
    """Result metadata for a single branch operation."""

    action: str
    score_before: float
    score_after: float
    became_done: bool


class SimulatedBranchGenerator:
    """Simple local generator used when no external LLM is wired."""

    def __init__(
        self,
        rng: random.Random,
        max_depth: int,
        finish_prob_base: float,
        answer_noise: float,
    ) -> None:
        self.rng = rng
        self.max_depth = max_depth
        self.finish_prob_base = finish_prob_base
        self.answer_noise = answer_noise

    def init_branch(self, branch_id: str) -> BranchState:
        latent_quality = self.rng.uniform(0.2, 0.95)
        return BranchState(branch_id=branch_id, latent_quality=latent_quality, score=latent_quality)

    def expand(self, branch: BranchState, question: str, gold_answer: str) -> BranchActionResult:  # noqa: ARG002
        if branch.is_done or branch.is_pruned:
            return BranchActionResult("expand", branch.score, branch.score, branch.is_done)

        score_before = branch.score
        branch.score_history.append(score_before)
        branch.depth_history.append(branch.depth)
        branch.action_history.append("expand")
        branch.steps.append(f"step_{branch.depth + 1}")
        drift = self.rng.uniform(-0.05, 0.08)
        branch.score = min(1.0, max(0.0, branch.score + drift))
        branch.recent_delta = branch.score - score_before
        branch.stalled_steps = branch.stalled_steps + 1 if branch.recent_delta <= 0.005 else 0

        finish_prob = min(0.95, self.finish_prob_base + 0.1 * branch.depth + 0.25 * branch.latent_quality)
        should_finish = branch.depth >= self.max_depth or self.rng.random() < finish_prob

        if should_finish:
            branch.is_done = True
            is_correct = self.rng.random() < max(0.05, branch.score - self.answer_noise)
            branch.predicted_answer = gold_answer if is_correct else self._make_wrong_answer(gold_answer)
        branch.trace_events.append(
            {
                "action": "expand",
                "prompt_text": question,
                "response_text": branch.steps[-1] if branch.steps else "",
                "reasoning_text": "\n".join(branch.steps),
                "extracted_answer": branch.predicted_answer,
                "branch_depth": branch.depth,
            }
        )

        return BranchActionResult("expand", score_before, branch.score, branch.is_done)

    def verify(self, branch: BranchState, question: str) -> BranchActionResult:  # noqa: ARG002
        score_before = branch.score
        branch.verify_count += 1
        branch.score_history.append(score_before)
        branch.depth_history.append(branch.depth)
        branch.action_history.append("verify")
        correction = (branch.latent_quality - branch.score) * 0.35
        jitter = self.rng.uniform(-0.03, 0.03)
        branch.score = min(1.0, max(0.0, branch.score + correction + jitter))
        branch.recent_delta = branch.score - score_before
        branch.trace_events.append(
            {
                "action": "verify",
                "prompt_text": question,
                "response_text": "",
                "reasoning_text": "\n".join(branch.steps),
                "extracted_answer": branch.predicted_answer,
                "branch_depth": branch.depth,
            }
        )
        return BranchActionResult("verify", score_before, branch.score, branch.is_done)

    @staticmethod
    def prune(branch: BranchState) -> BranchActionResult:
        score_before = branch.score
        branch.is_pruned = True
        return BranchActionResult("prune", score_before, branch.score, branch.is_done)

    def _make_wrong_answer(self, gold_answer: str) -> str:
        try:
            value = int(float(gold_answer))
            return str(value + self.rng.choice([-3, -2, -1, 1, 2, 3]))
        except ValueError:
            return f"wrong_{self.rng.randint(0, 999)}"

    def generate_program_of_thought_answer(self, question: str) -> dict[str, Any]:
        """PAL/PoT-style: synthesize trivial code and execute in the local sandbox."""
        nums = [int(x) for x in re.findall(r"\d+", question)]
        if len(nums) >= 2:
            code = f"print({nums[0]} + {nums[1]})"
        elif len(nums) == 1:
            code = f"print({nums[0]})"
        else:
            code = "print(0)"
        exec_out = run_restricted_python(code, timeout_seconds=1.0)
        ans = self._extract_last_numeric(exec_out["stdout"])
        return {
            "ok": exec_out["exception"] is None,
            "python_code": code,
            "stdout": exec_out["stdout"],
            "stderr": exec_out["stderr"],
            "exception": exec_out["exception"],
            "prediction": ans,
            "suitable": True,
            "cost_units": {"generation": 1, "execution": 1},
        }

    @staticmethod
    def _extract_last_numeric(text: str) -> str | None:
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?", text.replace(",", ""))
        return nums[-1] if nums else None


class APIBranchGenerator:
    """Provisional API-backed branch generator and verifier."""

    def __init__(
        self,
        api_key: str | None,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: int = 45,
        base_url: str | None = None,
        provider: str = "openai",
        *,
        expand_prompt_variant: str = "default",
        retry_max_attempts: int = 4,
        retry_base_delay_seconds: float = 1.25,
        retry_backoff_multiplier: float = 2.0,
        retry_max_delay_seconds: float = 20.0,
        retry_jitter_seconds: float = 0.35,
    ) -> None:
        self.provider = provider.strip().lower()
        self.api_key = api_key
        if self.provider == "gemini":
            default_base_url = "https://generativelanguage.googleapis.com/v1beta"
        elif self.provider == "cohere":
            default_base_url = "https://api.cohere.com/v2"
        elif self.provider == "cerebras":
            default_base_url = "https://api.cerebras.ai/v1"
        elif self.provider == "mistral":
            default_base_url = "https://api.mistral.ai/v1"
        elif self.provider == "groq":
            default_base_url = "https://api.groq.com/openai/v1"
        elif self.provider == "azure_openai":
            default_base_url = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://api.openai.com/v1")
        elif self.provider == "fireworks":
            default_base_url = os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
        elif self.provider == "cloudrift_ai":
            default_base_url = os.environ.get("CLOUDRIFT_BASE_URL", "https://inference.cloudrift.ai/v1")
        else:
            default_base_url = "https://api.openai.com/v1"
        self.base_url = (base_url or default_base_url).rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_api_calls = 0
        self.total_retry_attempts = 0
        self.last_request_meta: dict[str, Any] = {}
        self.last_prompt_text: str = ""
        self.last_response_text: str = ""
        self.last_action_type: str = ""
        self.last_expand_answer_extraction_source: str = ""
        self.last_verify_answer_extraction_source: str = ""
        self.expand_prompt_variant = str(expand_prompt_variant or "default").strip().lower()
        self.retry_max_attempts = max(1, int(retry_max_attempts))
        self.retry_base_delay_seconds = max(0.01, float(retry_base_delay_seconds))
        self.retry_backoff_multiplier = max(1.0, float(retry_backoff_multiplier))
        self.retry_max_delay_seconds = max(0.01, float(retry_max_delay_seconds))
        self.retry_jitter_seconds = max(0.0, float(retry_jitter_seconds))

    def reset_usage_counters(self) -> None:
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_api_calls = 0
        self.total_retry_attempts = 0
        self.last_request_meta = {}

    def snapshot_usage_counters(self) -> dict[str, int]:
        return {
            "input_tokens": int(self.total_input_tokens),
            "output_tokens": int(self.total_output_tokens),
            "total_tokens": int(self.total_input_tokens + self.total_output_tokens),
            "api_calls": int(self.total_api_calls),
            "retry_attempts": int(self.total_retry_attempts),
        }

    def init_branch(self, branch_id: str) -> BranchState:
        return BranchState(branch_id=branch_id, latent_quality=0.5, score=0.5)

    def expand(self, branch: BranchState, question: str, gold_answer: str) -> BranchActionResult:  # noqa: ARG002
        if branch.is_done or branch.is_pruned:
            return BranchActionResult("expand", branch.score, branch.score, branch.is_done)

        score_before = branch.score
        prompt = self._expand_prompt(question, branch)
        payload = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": self.max_tokens,
            "text": {"format": {"type": "json_object"}},
            "temperature": self.temperature,
        }
        text = self._call_api(payload, prompt=prompt)
        self.last_prompt_text = prompt
        self.last_response_text = text
        self.last_action_type = "expand"
        data = self._safe_json(text)
        merged = self._merge_wrapped_json_dicts(data)

        action = str(merged.get("action", "continue") or "continue").strip().lower()
        step = str(merged.get("step", "") or merged.get("rationale_short", "") or "").strip()
        if len(step) > 500:
            step = step[:500]
        answer, extraction_source = self._resolve_expand_answer(text, merged, expand_prompt_variant=self.expand_prompt_variant)
        self.last_expand_answer_extraction_source = extraction_source
        confidence = self._clip01(self._to_float(merged.get("confidence", branch.score)))

        if step:
            branch.steps.append(step)
        elif action != "final":
            branch.steps.append("model_step_missing")

        branch.score = 0.6 * branch.score + 0.4 * confidence

        if action == "final" or answer:
            branch.is_done = True
            tail = self._extract_last_number(step) if step else ""
            digit_tail = tail if (tail and re.search(r"\d", str(tail))) else ""
            merged_pred = answer or digit_tail
            branch.predicted_answer = merged_pred if merged_pred else None
        trace_evt: dict[str, Any] = {
            "action": "expand",
            "prompt_text": prompt,
            "response_text": text,
            "reasoning_text": "\n".join(branch.steps),
            "extracted_answer": branch.predicted_answer,
            "branch_depth": branch.depth,
            "expand_answer_extraction_source": extraction_source,
        }
        # Optional unit-track contract fields (no-op for non unit-track prompts).
        trace_evt["entity_ledger"] = merged.get("entity_ledger") if isinstance(merged.get("entity_ledger"), list) else []
        trace_evt["target_entity"] = str(merged.get("target_entity") or "").strip()
        trace_evt["target_unit"] = str(merged.get("target_unit") or "").strip()
        trace_evt["unit_consistency_status"] = str(merged.get("unit_consistency_status") or "").strip()
        trace_evt["unit_consistency_notes"] = str(merged.get("unit_consistency_notes") or "").strip()
        trace_evt["unit_tracked_answer"] = self._stringify_scalar_answer_value(merged.get("unit_tracked_answer"))
        # Optional PAL/code-first contract fields (no-op for non-PAL prompts).
        trace_evt["pal_code"] = str(merged.get("code") or "").strip()
        trace_evt["pal_json_answer"] = self._stringify_scalar_answer_value(merged.get("answer"))
        try:
            trace_evt["pal_confidence"] = float(merged.get("confidence", 0.0) or 0.0)
        except Exception:
            trace_evt["pal_confidence"] = 0.0
        if self.expand_prompt_variant == "numeric_leaf":
            nls = str(merged.get("numeric_leaf_status") or "").strip().lower()
            nlv = self._stringify_scalar_answer_value(merged.get("numeric_leaf_value"))
            nl_src = "model_json"
            if not nlv and step:
                lv, ltag = extract_labeled_numeric_leaf_from_step(step)
                if lv:
                    nlv, nl_src = lv, ltag
            trace_evt["numeric_leaf_status"] = nls or None
            trace_evt["numeric_leaf_value"] = nlv or None
            trace_evt["numeric_leaf_source"] = nl_src
        branch.trace_events.append(trace_evt)

        return BranchActionResult("expand", score_before, branch.score, branch.is_done)

    def verify(self, branch: BranchState, question: str) -> BranchActionResult:
        score_before = branch.score
        prompt = self._verify_prompt(question, branch)
        payload = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": self.max_tokens,
            "text": {"format": {"type": "json_object"}},
            "temperature": min(0.2, self.temperature),
        }
        text = self._call_api(payload, prompt=prompt)
        self.last_prompt_text = prompt
        self.last_response_text = text
        self.last_action_type = "verify"
        data = self._safe_json(text)
        merged = self._merge_wrapped_json_dicts(data)
        confidence = self._clip01(self._to_float(merged.get("confidence", branch.score)))
        maybe_answer, verify_extraction_source = self._resolve_verify_answer(text, merged)
        self.last_verify_answer_extraction_source = verify_extraction_source

        branch.score = 0.5 * branch.score + 0.5 * confidence
        if maybe_answer and branch.predicted_answer is None:
            branch.predicted_answer = maybe_answer
        branch.trace_events.append(
            {
                "action": "verify",
                "prompt_text": prompt,
                "response_text": text,
                "reasoning_text": "\n".join(branch.steps),
                "extracted_answer": branch.predicted_answer,
                "branch_depth": branch.depth,
                "verify_answer_extraction_source": verify_extraction_source,
            }
        )
        return BranchActionResult("verify", score_before, branch.score, branch.is_done)

    @staticmethod
    def prune(branch: BranchState) -> BranchActionResult:
        score_before = branch.score
        branch.is_pruned = True
        return BranchActionResult("prune", score_before, branch.score, branch.is_done)

    def _call_api(self, payload: dict, prompt: str) -> str:
        _consume_logical_api_call_budget()
        if self.provider == "gemini":
            return self._call_gemini_api(prompt)
        if self.provider == "cohere":
            return self._call_cohere_chat_api(prompt)
        if self.provider == "cerebras":
            return self._call_cerebras_chat_api(prompt)
        if self.provider == "mistral":
            return self._call_mistral_chat_api(prompt)
        if self.provider == "groq":
            return self._call_groq_chat_api(prompt)
        if self.provider == "azure_openai":
            return self._call_azure_chat_api(prompt)
        if self.provider in {"fireworks", "cloudrift_ai", "cloudrift"}:
            return self._call_openai_compatible_chat_api(prompt)
        return self._call_responses_api(payload)

    def _compute_retry_delay_seconds(self, attempt_idx: int, *, retry_after_hint_seconds: float = 0.0) -> float:
        # attempt_idx is zero-based. Retry waits are exponential and bounded.
        base = self.retry_base_delay_seconds * (self.retry_backoff_multiplier ** max(0, attempt_idx))
        bounded = min(self.retry_max_delay_seconds, base)
        jitter = random.uniform(0.0, self.retry_jitter_seconds) if self.retry_jitter_seconds > 0 else 0.0
        return float(max(bounded + jitter, float(retry_after_hint_seconds)))

    def _log_retry_attempt(
        self,
        *,
        provider: str,
        attempt_number: int,
        max_attempts: int,
        reason: str,
        wait_seconds: float,
    ) -> None:
        print(
            f"[api-retry] provider={provider} attempt={attempt_number}/{max_attempts} "
            f"wait_seconds={wait_seconds:.3f} reason={reason}",
            flush=True,
        )

    def _call_cohere_chat_api(self, prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }

        retry_attempts = self.retry_max_attempts
        body: dict | None = None
        for attempt in range(retry_attempts):
            req = request.Request(
                f"{self.base_url}/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    usage = body.get("usage", {}) if isinstance(body, dict) else {}
                    tokens = usage.get("tokens", {}) if isinstance(usage, dict) else {}
                    billed = usage.get("billed_units", {}) if isinstance(usage, dict) else {}
                    in_tok = tokens.get("input_tokens", billed.get("input_tokens", 0)) if isinstance(tokens, dict) else 0
                    out_tok = tokens.get("output_tokens", billed.get("output_tokens", 0)) if isinstance(tokens, dict) else 0
                    try:
                        in_tok_i = int(in_tok or 0)
                    except Exception:
                        in_tok_i = 0
                    try:
                        out_tok_i = int(out_tok or 0)
                    except Exception:
                        out_tok_i = 0
                    self.total_input_tokens += in_tok_i
                    self.total_output_tokens += out_tok_i
                    self.total_api_calls += 1
                    self.total_retry_attempts += int(attempt)
                    self.last_request_meta = {
                        "attempts": int(attempt + 1),
                        "input_tokens": in_tok_i,
                        "output_tokens": out_tok_i,
                    }
                break
            except error.HTTPError as exc:  # pragma: no cover - network path
                err_body = exc.read().decode("utf-8", errors="ignore")
                is_retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
                if is_retryable and attempt < retry_attempts - 1:
                    retry_after_seconds = 0.0
                    if exc.code == 429:
                        try:
                            retry_after_raw = str(exc.headers.get("Retry-After", "0") or "0").strip()
                            retry_after_seconds = float(retry_after_raw) if retry_after_raw else 0.0
                        except Exception:
                            retry_after_seconds = 0.0
                    wait_seconds = self._compute_retry_delay_seconds(attempt, retry_after_hint_seconds=retry_after_seconds)
                    self._log_retry_attempt(
                        provider=self.provider,
                        attempt_number=int(attempt + 1),
                        max_attempts=int(retry_attempts),
                        reason=f"http_{exc.code}",
                        wait_seconds=wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise RuntimeError(f"Cohere API HTTPError {exc.code}: {err_body[:500]}") from exc
            except Exception as exc:  # pragma: no cover - network path
                if attempt < retry_attempts - 1:
                    retryable = isinstance(exc, (TimeoutError, socket.timeout, error.URLError, ConnectionError))
                    exc_text = str(exc).lower()
                    if (not retryable) and ("timed out" in exc_text or "timeout" in exc_text or "temporar" in exc_text):
                        retryable = True
                    if retryable:
                        wait_seconds = self._compute_retry_delay_seconds(attempt)
                        self._log_retry_attempt(
                            provider=self.provider,
                            attempt_number=int(attempt + 1),
                            max_attempts=int(retry_attempts),
                            reason=type(exc).__name__,
                            wait_seconds=wait_seconds,
                        )
                        time.sleep(wait_seconds)
                        continue
                    raise RuntimeError(f"Cohere API request failed (non-retryable): {exc}") from exc
                raise RuntimeError(f"Cohere API request failed: {exc}") from exc
        if body is None:  # pragma: no cover - defensive
            raise RuntimeError("Cohere API request failed after retries.")

        message = body.get("message", {})
        content = message.get("content", [])
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(str(item.get("text", "")))
        if texts:
            return "\n".join(texts)
        raise RuntimeError("Cohere API returned no text output.")

    def _call_cerebras_chat_api(self, prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        # Avoid Cloudflare WAF blocks (HTTP 403 error code 1010) by setting a common User-Agent
        headers["User-Agent"] = "python-requests/2.31.0"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        retry_attempts = 4
        body: dict | None = None
        for attempt in range(retry_attempts):
            req = request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                break
            except error.HTTPError as exc:
                # Read body for diagnostics
                err_body = exc.read().decode("utf-8", errors="ignore")
                # If rate-limited, honor Retry-After header when present
                if exc.code == 429 and attempt < retry_attempts - 1:
                    try:
                        retry_after = int(exc.headers.get("Retry-After", "0") or "0")
                    except Exception:
                        retry_after = 0
                    wait = max(1.25 * (attempt + 1), retry_after + 1 if retry_after > 0 else 0)
                    time.sleep(wait)
                    continue
                if exc.code in {408, 500, 502, 503, 504} and attempt < retry_attempts - 1:
                    time.sleep(1.25 * (attempt + 1))
                    continue
                raise RuntimeError(f"Cerebras API HTTPError {exc.code}: {err_body[:500]}") from exc
            except Exception as exc:
                if attempt < retry_attempts - 1:
                    time.sleep(1.25 * (attempt + 1))
                    continue
                raise RuntimeError(f"Cerebras API request failed: {exc}") from exc

        if body is None:
            raise RuntimeError("Cerebras API request failed after retries.")

        # Cerebras returns choices -> message -> content
        choices = body.get("choices", []) if isinstance(body, dict) else []
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
        raise RuntimeError("Cerebras API returned no text output.")

    def _call_mistral_chat_api(self, prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return only valid JSON matching the requested schema."},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        retry_attempts = self.retry_max_attempts
        body: dict | None = None
        for attempt in range(retry_attempts):
            req = request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    usage = body.get("usage", {}) if isinstance(body, dict) else {}
                    prompt_tokens = 0
                    completion_tokens = 0
                    if isinstance(usage, dict):
                        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
                        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
                    self.total_input_tokens += prompt_tokens
                    self.total_output_tokens += completion_tokens
                    self.total_api_calls += 1
                    self.total_retry_attempts += int(attempt)
                    self.last_request_meta = {
                        "attempts": int(attempt + 1),
                        "input_tokens": int(prompt_tokens),
                        "output_tokens": int(completion_tokens),
                    }
                break
            except error.HTTPError as exc:  # pragma: no cover - network path
                err_body = exc.read().decode("utf-8", errors="ignore")
                is_retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
                if is_retryable and attempt < retry_attempts - 1:
                    retry_after_seconds = 0.0
                    if exc.code == 429:
                        try:
                            retry_after_raw = str(exc.headers.get("Retry-After", "0") or "0").strip()
                            retry_after_seconds = float(retry_after_raw) if retry_after_raw else 0.0
                        except Exception:
                            retry_after_seconds = 0.0
                    wait_seconds = self._compute_retry_delay_seconds(attempt, retry_after_hint_seconds=retry_after_seconds)
                    self._log_retry_attempt(
                        provider=self.provider,
                        attempt_number=int(attempt + 1),
                        max_attempts=int(retry_attempts),
                        reason=f"http_{exc.code}",
                        wait_seconds=wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise RuntimeError(f"Mistral API HTTPError {exc.code}: {err_body[:500]}") from exc
            except Exception as exc:  # pragma: no cover - network path
                if attempt < retry_attempts - 1:
                    retryable = isinstance(exc, (TimeoutError, socket.timeout, error.URLError, ConnectionError))
                    exc_text = str(exc).lower()
                    if (not retryable) and ("timed out" in exc_text or "timeout" in exc_text or "temporar" in exc_text):
                        retryable = True
                    if retryable:
                        wait_seconds = self._compute_retry_delay_seconds(attempt)
                        self._log_retry_attempt(
                            provider=self.provider,
                            attempt_number=int(attempt + 1),
                            max_attempts=int(retry_attempts),
                            reason=type(exc).__name__,
                            wait_seconds=wait_seconds,
                        )
                        time.sleep(wait_seconds)
                        continue
                    raise RuntimeError(f"Mistral API request failed (non-retryable): {exc}") from exc
                raise RuntimeError(f"Mistral API request failed: {exc}") from exc

        if body is None:  # pragma: no cover - defensive
            raise RuntimeError("Mistral API request failed after retries.")

        choices = body.get("choices", []) if isinstance(body, dict) else []
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
        raise RuntimeError("Mistral API returned no text output.")

    def _call_groq_chat_api(self, prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return only valid JSON matching the requested schema."},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }

        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - network path
            err_body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Groq API HTTPError {exc.code}: {err_body[:500]}") from exc
        except Exception as exc:  # pragma: no cover - network path
            raise RuntimeError(f"Groq API request failed: {exc}") from exc

        choices = body.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
        raise RuntimeError("Groq API returned no text output.")

    def _call_azure_chat_api(self, prompt: str) -> str:
        """Call Azure OpenAI via the /openai/v1-compatible /chat/completions endpoint.

        Uses openai.OpenAI(base_url=AZURE_OPENAI_ENDPOINT) pattern, NOT AzureOpenAI,
        because the endpoint already contains /openai/v1 and the AzureOpenAI client
        would double-prefix the path causing 404.
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,  # Azure deployment name, e.g. "gpt-4.1-mini"
            "messages": [
                {"role": "system", "content": "Return only valid JSON matching the requested schema."},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,  # gpt-4.1-mini supports max_tokens (not max_completion_tokens)
        }

        retry_attempts = self.retry_max_attempts
        body: dict | None = None
        for attempt in range(retry_attempts):
            req = request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    usage = body.get("usage", {}) if isinstance(body, dict) else {}
                    prompt_tokens = int((usage.get("prompt_tokens") or 0)) if isinstance(usage, dict) else 0
                    completion_tokens = int((usage.get("completion_tokens") or 0)) if isinstance(usage, dict) else 0
                    self.total_input_tokens += prompt_tokens
                    self.total_output_tokens += completion_tokens
                    self.total_api_calls += 1
                    self.total_retry_attempts += int(attempt)
                    self.last_request_meta = {
                        "attempts": int(attempt + 1),
                        "input_tokens": int(prompt_tokens),
                        "output_tokens": int(completion_tokens),
                    }
                break
            except error.HTTPError as exc:  # pragma: no cover - network path
                err_body = exc.read().decode("utf-8", errors="ignore")
                is_retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
                if is_retryable and attempt < retry_attempts - 1:
                    retry_after_seconds = 0.0
                    try:
                        retry_after_seconds = float(exc.headers.get("Retry-After", "0") or "0")
                    except Exception:
                        retry_after_seconds = 0.0
                    wait_seconds = self._compute_retry_delay_seconds(
                        attempt, retry_after_hint_seconds=retry_after_seconds
                    )
                    self._log_retry_attempt(
                        provider="azure_openai",
                        attempt_number=attempt + 1,
                        max_attempts=retry_attempts,
                        reason=f"http_{exc.code}",
                        wait_seconds=wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise RuntimeError(f"Azure OpenAI API request failed (non-retryable): {exc}") from exc
            except Exception as exc:  # pragma: no cover - network path
                if attempt < retry_attempts - 1:
                    wait_seconds = self._compute_retry_delay_seconds(attempt)
                    self._log_retry_attempt(
                        provider="azure_openai",
                        attempt_number=attempt + 1,
                        max_attempts=retry_attempts,
                        reason=f"{type(exc).__name__}",
                        wait_seconds=wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise RuntimeError(f"Azure OpenAI API request failed: {exc}") from exc

        if body is None:  # pragma: no cover - defensive
            raise RuntimeError("Azure OpenAI API request failed after retries.")

        choices = body.get("choices", []) if isinstance(body, dict) else []
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
        raise RuntimeError("Azure OpenAI API returned no text output.")

    def _call_openai_compatible_chat_api(self, prompt: str) -> str:
        """Generic OpenAI-compatible /v1/chat/completions call (Fireworks, Cloudrift AI, etc.)."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return only valid JSON matching the requested schema."},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        retry_attempts = self.retry_max_attempts
        body: dict | None = None
        for attempt in range(retry_attempts):
            req = request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    usage = body.get("usage", {}) if isinstance(body, dict) else {}
                    prompt_tokens = int((usage.get("prompt_tokens") or 0)) if isinstance(usage, dict) else 0
                    completion_tokens = int((usage.get("completion_tokens") or 0)) if isinstance(usage, dict) else 0
                    self.total_input_tokens += prompt_tokens
                    self.total_output_tokens += completion_tokens
                    self.total_api_calls += 1
                    self.total_retry_attempts += int(attempt)
                    self.last_request_meta = {
                        "attempts": int(attempt + 1),
                        "input_tokens": int(prompt_tokens),
                        "output_tokens": int(completion_tokens),
                    }
                break
            except error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="ignore")
                is_retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
                if is_retryable and attempt < retry_attempts - 1:
                    retry_after_seconds = 0.0
                    try:
                        retry_after_seconds = float(exc.headers.get("Retry-After", "0") or "0")
                    except Exception:
                        retry_after_seconds = 0.0
                    wait_seconds = self._compute_retry_delay_seconds(
                        attempt, retry_after_hint_seconds=retry_after_seconds
                    )
                    self._log_retry_attempt(
                        provider=self.provider,
                        attempt_number=attempt + 1,
                        max_attempts=retry_attempts,
                        reason=f"http_{exc.code}",
                        wait_seconds=wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise RuntimeError(
                    f"{self.provider} API request failed (http {exc.code}): {err_body[:400]}"
                ) from exc
            except Exception as exc:
                if attempt < retry_attempts - 1:
                    wait_seconds = self._compute_retry_delay_seconds(attempt)
                    self._log_retry_attempt(
                        provider=self.provider,
                        attempt_number=attempt + 1,
                        max_attempts=retry_attempts,
                        reason=f"{type(exc).__name__}",
                        wait_seconds=wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise RuntimeError(f"{self.provider} API request failed: {exc}") from exc

        if body is None:
            raise RuntimeError(f"{self.provider} API request failed after retries.")

        choices = body.get("choices", []) if isinstance(body, dict) else []
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
            # Reasoning/thinking models (e.g. Cloudrift Qwen3) return content=null
            # and put the actual output in message.reasoning instead.
            reasoning = message.get("reasoning")
            if isinstance(reasoning, str) and reasoning.strip():
                return reasoning
        raise RuntimeError(f"{self.provider} API returned no text output.")

    def _call_responses_api(self, payload: dict) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        retry_attempts = 4
        body: dict | None = None
        for attempt in range(retry_attempts):
            req = request.Request(
                f"{self.base_url}/responses",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                break
            except error.HTTPError as exc:  # pragma: no cover - network path
                err_body = exc.read().decode("utf-8", errors="ignore")
                if exc.code in {408, 429, 500, 502, 503, 504} and attempt < retry_attempts - 1:
                    time.sleep(1.25 * (attempt + 1))
                    continue
                raise RuntimeError(f"OpenAI API HTTPError {exc.code}: {err_body[:500]}") from exc
            except Exception as exc:  # pragma: no cover - network path
                if attempt < retry_attempts - 1:
                    time.sleep(1.25 * (attempt + 1))
                    continue
                raise RuntimeError(f"OpenAI API request failed: {exc}") from exc
        if body is None:  # pragma: no cover - defensive
            raise RuntimeError("OpenAI API request failed after retries.")

        texts: list[str] = []
        for item in body.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content.get("text", ""))
        if texts:
            return "\n".join(texts)

        fallback = body.get("output_text")
        if isinstance(fallback, str) and fallback.strip():
            return fallback
        raise RuntimeError("OpenAI API returned no text output.")

    def _call_gemini_api(self, prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
                "responseMimeType": "application/json",
            },
        }
        endpoint = f"{self.base_url}/models/{self.model}:generateContent"
        if self.api_key:
            endpoint = f"{endpoint}?key={self.api_key}"
        retry_attempts = 4
        body: dict | None = None
        for attempt in range(retry_attempts):
            req = request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                break
            except error.HTTPError as exc:  # pragma: no cover - network path
                err_body = exc.read().decode("utf-8", errors="ignore")
                if exc.code in {408, 429, 500, 502, 503, 504} and attempt < retry_attempts - 1:
                    time.sleep(1.25 * (attempt + 1))
                    continue
                raise RuntimeError(f"Gemini API HTTPError {exc.code}: {err_body[:500]}") from exc
            except Exception as exc:  # pragma: no cover - network path
                if attempt < retry_attempts - 1:
                    time.sleep(1.25 * (attempt + 1))
                    continue
                raise RuntimeError(f"Gemini API request failed: {exc}") from exc
        if body is None:  # pragma: no cover - defensive
            raise RuntimeError("Gemini API request failed after retries.")

        texts: list[str] = []
        for candidate in body.get("candidates", []):
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text)
        if texts:
            return "\n".join(texts)
        raise RuntimeError("Gemini API returned no text output.")

    @staticmethod
    def _strip_json_markdown_fence(text: str) -> str:
        t = str(text or "").strip()
        m = _JSON_FENCE_FULL.match(t)
        if m:
            return m.group(1).strip()
        emb = _JSON_FENCE_EMBED.search(t)
        if emb:
            return emb.group(1).strip()
        return t

    @staticmethod
    def _extract_first_json_object(text: str) -> str | None:
        """Return the first balanced {...} slice, respecting quoted strings."""
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_str = False
        esc = False
        quote = ""
        i = start
        while i < len(text):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == quote:
                    in_str = False
                i += 1
                continue
            if c in "\"'":
                in_str = True
                quote = c
                i += 1
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
            i += 1
        return None

    @staticmethod
    def _merge_wrapped_json_dicts(data: dict[str, Any]) -> dict[str, Any]:
        """Flatten one level of common wrapper keys (``response``, ``result``, …)."""
        if not isinstance(data, dict):
            return {}
        merged: dict[str, Any] = dict(data)
        for wrap_key in ("response", "output", "message", "parsed", "result"):
            inner = data.get(wrap_key)
            if isinstance(inner, dict):
                for k, v in inner.items():
                    if k not in merged or merged.get(k) in (None, "", [], {}):
                        merged[k] = v
            elif wrap_key == "result" and isinstance(inner, str) and inner.strip():
                if not APIBranchGenerator._first_nonempty_answer_for_keys(
                    merged, _EXPAND_ANSWER_KEYS
                ):
                    merged.setdefault("answer", inner.strip())
        return merged

    @staticmethod
    def _stringify_scalar_answer_value(v: object) -> str:
        if v is None or isinstance(v, (dict, list)):
            return ""
        if isinstance(v, bool):
            return ""
        if isinstance(v, (int, float)):
            if isinstance(v, float) and v.is_integer():
                return str(int(v))
            return str(v)
        s = str(v).strip()
        if s.lower() in {"null", "none", "n/a", ""}:
            return ""
        return s

    @staticmethod
    def _first_nonempty_answer_for_keys(merged: dict[str, Any], keys: tuple[str, ...]) -> str:
        for k in keys:
            s = APIBranchGenerator._stringify_scalar_answer_value(merged.get(k))
            if s:
                return s
        return ""

    @staticmethod
    def _expand_answer_fallback_raw_text(raw_text: str) -> str:
        """Legacy name: delegates to plain-text fallback (phrase / boxed / #### / prose)."""
        return APIBranchGenerator._plain_text_answer_fallback(raw_text)

    @staticmethod
    def _verify_answer_fallback_raw_text(raw_text: str) -> str:
        return APIBranchGenerator._plain_text_answer_fallback(raw_text)

    @staticmethod
    def _plain_text_answer_fallback(raw_text: str) -> str:
        """Extract a final numeric answer from non-JSON or malformed model text (no gold)."""
        t = str(raw_text or "").strip()
        if not t:
            return ""
        m = _FINAL_ANS_PHRASE_RE.search(t)
        if m:
            return m.group(1).replace(",", "")
        if "\\boxed" in t or "####" in t:
            ext = extract_final_answer(t)
            return ext.strip() if ext else ""
        stripped = t.lstrip()
        rs = stripped.rstrip()
        if stripped.startswith("{") and rs.endswith("}"):
            # Likely JSON object: avoid last-number heuristics on the whole blob (e.g. confidence 0.9).
            return ""
        if stripped.startswith("{") and not rs.endswith("}"):
            # Truncated / invalid JSON-looking prefix: do not mine spurious numbers from the fragment.
            return ""
        ext = extract_final_answer(t)
        return ext.strip() if ext else ""

    @staticmethod
    def _reasoning_blob_from_merged(merged: dict[str, Any], keys: tuple[str, ...]) -> str:
        parts: list[str] = []
        for key in keys:
            v = merged.get(key)
            if isinstance(v, str) and v.strip():
                parts.append(v.strip())
        return "\n".join(parts)

    @classmethod
    def _resolve_expand_answer(
        cls,
        raw_text: str,
        merged: dict[str, Any],
        *,
        expand_prompt_variant: str = "default",
    ) -> tuple[str, str]:
        """Return (answer, extraction_source_tag) for expand() (gold-free)."""
        for k in _EXPAND_ANSWER_KEYS:
            s = cls._stringify_scalar_answer_value(merged.get(k))
            if s:
                tag = "api_json_final_answer" if k == "final_answer" else "api_json_answer"
                return s, tag
        action_l = str(merged.get("action", "") or "").strip().lower()
        if expand_prompt_variant == "numeric_leaf":
            nlv = cls._stringify_scalar_answer_value(merged.get("numeric_leaf_value"))
            nls = str(merged.get("numeric_leaf_status") or "").strip().lower()
            if action_l == "final" and nlv:
                if nls == "final" or nls == "":
                    return nlv, "api_json_numeric_leaf_final"
        blob = cls._reasoning_blob_from_merged(merged, _EXPAND_REASONING_TEXT_KEYS)
        if expand_prompt_variant == "numeric_leaf" and blob and action_l != "continue":
            lbl, lsrc = extract_labeled_numeric_leaf_from_step(blob)
            if lbl:
                return lbl, lsrc
        if blob:
            if expand_prompt_variant == "numeric_leaf":
                structured_answer_signal = bool(
                    ANSWER_PATTERN.search(blob)
                    or ("\\boxed" in blob)
                    or ("####" in blob)
                    or (action_l == "final")
                )
            else:
                structured_answer_signal = bool(
                    ANSWER_PATTERN.search(blob)
                    or ("\\boxed" in blob)
                    or ("####" in blob)
                    or (action_l == "final")
                    or _REASONING_NUMERIC_MINING_HINT.search(blob)
                )
            if structured_answer_signal:
                ext = extract_final_answer(blob).strip()
                if ext and re.search(r"\d", ext):
                    return ext, "api_json_reasoning_fallback"
                if expand_prompt_variant != "numeric_leaf":
                    ln = cls._extract_last_number(blob)
                    if ln and re.search(r"\d", str(ln)):
                        return str(ln), "api_json_reasoning_fallback"
        fb = cls._plain_text_answer_fallback(raw_text)
        if fb:
            return fb, "api_plain_text_fallback"
        return "", "api_parse_failed_no_answer"

    @classmethod
    def _resolve_verify_answer(cls, raw_text: str, merged: dict[str, Any]) -> tuple[str, str]:
        for k in _VERIFY_ANSWER_KEYS:
            s = cls._stringify_scalar_answer_value(merged.get(k))
            if s:
                tag = "api_json_final_answer" if k == "final_answer" else "api_json_answer"
                return s, tag
        blob = cls._reasoning_blob_from_merged(merged, ("rationale_short", "step", "reasoning"))
        if blob:
            structured_answer_signal = bool(
                ANSWER_PATTERN.search(blob)
                or ("\\boxed" in blob)
                or ("####" in blob)
                or _REASONING_NUMERIC_MINING_HINT.search(blob)
            )
            if structured_answer_signal:
                ext = extract_final_answer(blob).strip()
                if ext and re.search(r"\d", ext):
                    return ext, "api_json_reasoning_fallback"
                ln = cls._extract_last_number(blob)
                if ln and re.search(r"\d", str(ln)):
                    return str(ln), "api_json_reasoning_fallback"
        fb = cls._plain_text_answer_fallback(raw_text)
        if fb:
            return fb, "api_plain_text_fallback"
        return "", "api_parse_failed_no_answer"

    @staticmethod
    def _safe_json(text: str) -> dict:
        if not text or not str(text).strip():
            return {}
        t = APIBranchGenerator._strip_json_markdown_fence(str(text))
        try:
            obj = json.loads(t)
            if isinstance(obj, dict):
                return obj
            if isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict):
                        return item
            return {}
        except json.JSONDecodeError:
            pass
        balanced = APIBranchGenerator._extract_first_json_object(t)
        if balanced:
            try:
                obj = json.loads(balanced)
                if isinstance(obj, dict):
                    return obj
                if isinstance(obj, list):
                    for item in obj:
                        if isinstance(item, dict):
                            return item
                return {}
            except json.JSONDecodeError:
                pass
        match = re.search(r"\{.*\}", t, flags=re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group(0))
                if isinstance(obj, dict):
                    return obj
                if isinstance(obj, list):
                    for item in obj:
                        if isinstance(item, dict):
                            return item
                return {}
            except json.JSONDecodeError:
                pass
        return {}

    @staticmethod
    def _extract_last_number(text: str) -> str:
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?", text)
        return nums[-1] if nums else text.strip()

    @staticmethod
    def _to_float(v: object) -> float:
        try:
            return float(v)  # type: ignore[arg-type]
        except Exception:
            return 0.5

    @staticmethod
    def _clip01(v: float) -> float:
        return max(0.0, min(1.0, v))

    def _expand_prompt(self, question: str, branch: BranchState) -> str:
        prior = "\n".join(f"- {s}" for s in branch.steps[-3:]) or "(none)"
        if self.expand_prompt_variant == "numeric_leaf":
            return (
                "You are solving a GSM8K math word problem. Continue reasoning for ONE short step or finish with a final numeric answer.\n"
                "Every step must surface numeric progress: include EITHER a clearly labeled provisional/intermediate number "
                "OR a compact equation with its computed numeric result.\n"
                "If you can already determine the final numeric result from the question and prior reasoning, use action='final', "
                "put that number in answer, set numeric_leaf_status to 'final', and set numeric_leaf_value to the same number.\n"
                "Return strict JSON with keys: action, step, answer, confidence, numeric_leaf_status, numeric_leaf_value.\n"
                "- action: 'continue' or 'final'.\n"
                "- answer: empty unless action is 'final'; when final, answer must be non-empty.\n"
                "- confidence: 0..1.\n"
                "- numeric_leaf_status: one of 'final' | 'provisional' | 'equation_progress' | 'none'.\n"
                "- numeric_leaf_value: string or null. If action is 'continue', answer may be empty but numeric_leaf_value should "
                "carry the best numeric progress (provisional total, equation rhs, etc.) unless no numeric progress exists.\n"
                "If numeric_leaf_status is 'final', numeric_leaf_value should match answer.\n\n"
                f"Question:\n{question}\n\n"
                f"Current partial reasoning:\n{prior}\n"
            )
        return (
            "You are solving a GSM8K math word problem. Continue reasoning for ONE short step or finish with a final numeric answer. "
            "If you can already determine the final numeric result from the question and prior reasoning, use action='final' and put that number in answer (do not defer unnecessarily). "
            "Return strict JSON with keys: action, step, answer, confidence. "
            "action must be 'continue' or 'final'. answer should be empty unless final. confidence is 0..1.\n\n"
            f"Question:\n{question}\n\n"
            f"Current partial reasoning:\n{prior}\n"
        )

    def _verify_prompt(self, question: str, branch: BranchState) -> str:
        prior = "\n".join(f"- {s}" for s in branch.steps[-4:]) or "(none)"
        return (
            "You are a lightweight verifier for GSM8K reasoning. Assess if the current reasoning path seems correct. "
            "Return strict JSON with keys: confidence (0..1), candidate_answer, rationale_short. "
            "candidate_answer may be empty if unknown.\n\n"
            f"Question:\n{question}\n\n"
            f"Reasoning path:\n{prior}\n\n"
            f"Current predicted answer (if any): {branch.predicted_answer or ''}\n"
        )

    def generate_program_of_thought_answer(self, question: str) -> dict[str, Any]:
        """One-shot code generation + sandbox execution (PAL/PoT-style), separate from expand/verify."""
        prompt = (
            "Solve the question by writing short Python code (standard library only, no input(), no network). "
            "Return strict JSON with keys: python_code (string), explanation (one short sentence). "
            "python_code must print the final numeric answer as the only output or as the last printed line.\n\n"
            f"Question:\n{question}\n"
        )
        payload = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": max(256, self.max_tokens),
            "text": {"format": {"type": "json_object"}},
            "temperature": min(0.3, self.temperature),
        }
        text = self._call_api(payload, prompt=prompt)
        data = self._safe_json(text)
        code = str(data.get("python_code", "")).strip()
        if not code:
            return {
                "ok": False,
                "python_code": "",
                "stdout": "",
                "stderr": "",
                "exception": "missing_python_code",
                "prediction": None,
                "suitable": False,
                "cost_units": {"generation": 1, "execution": 0},
            }
        exec_out = run_restricted_python(code, timeout_seconds=2.0)
        pred = self._extract_last_number(exec_out["stdout"]) if exec_out["stdout"] else None
        ok = exec_out["exception"] is None and bool(pred)
        return {
            "ok": ok,
            "python_code": code,
            "stdout": exec_out["stdout"],
            "stderr": exec_out["stderr"],
            "exception": exec_out["exception"],
            "prediction": pred,
            "suitable": True,
            "cost_units": {"generation": 1, "execution": 1},
        }
