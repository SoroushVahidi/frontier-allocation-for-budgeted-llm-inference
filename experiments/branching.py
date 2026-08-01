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
    r"^\s*```(?:\w+)?\s*\r?\n?(.*)\r?\n?```\s*$",
    re.DOTALL,
)
_JSON_FENCE_EMBED = re.compile(r"```(?:\w+)?\s*\r?\n(.*?)```", re.DOTALL)
_FINAL_ANS_PHRASE_RE = re.compile(
    r"(?i)(?:final\s+answer|the\s+answer\s+is|answer\s+is)\s*[:=]?\s*([-+]?\d[\d,]*(?:\.\d+)?)",
)
_REASONING_NUMERIC_MINING_HINT = re.compile(
    r"(?i)\b(therefore|hence|in conclusion|overall|finally|total\s+is|answer\s+is|result\s+is)\b",
)
_MCQ_FINAL_LETTER_MARKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bfinal\s+answer\s*(?:is|:)\s*\(?([A-D])\)?\b"),
    re.compile(r"(?i)\bthe\s+answer\s+is\s*\(?([A-D])\)?\b"),
    re.compile(r"(?i)\banswer\s*:\s*\(?([A-D])\)?\b"),
    re.compile(r"\\boxed\{([A-D])\}"),
)
_STRATEGYQA_FINAL_BOOL_MARKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?im)^\s*final\s+answer\s*(?:is|:)\s*(true|false|yes|no)\s*$"),
    re.compile(r"(?im)^\s*answer\s*:\s*(true|false|yes|no)\s*$"),
    re.compile(r"(?im)^\s*final_answer\s*=\s*(true|false)\s*$"),
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

_MODEL_STEP_MISSING_SENTINEL = "model_step_missing"

_MCQ_MARKER = "Answer with a single letter (A, B, C, or D)."

# The exact instruction line scripts/build_strategyqa_problems_file.py::build_strategyqa_prompt()
# already appends to every StrategyQA question. Reusing it as a detection marker (same pattern
# as _MCQ_MARKER above) is purely additive -- no prompt-building code changes -- and lets
# extraction code recognize a StrategyQA question without threading a `dataset` parameter
# through expand()/verify().
_STRATEGYQA_MARKER = "Answer with exactly True or False."
# Deliberately narrower than scripts/build_strategyqa_problems_file.py::normalize_boolean_answer
# (which also accepts "0"/"1"/"y"/"n" -- a scoring-layer helper for comparing two already-
# independently-parsed boolean-ish values, gold included). This set gates what may ever be
# COMMITTED as a StrategyQA branch.predicted_answer / action_log candidate_answer in the first
# place: a bare digit must never count as a valid StrategyQA final answer, even though it is an
# acceptable gold-normalization input elsewhere -- see sanitize_strategyqa_final_answer().
_STRATEGYQA_TRUE_STRINGS = {"true", "yes"}
_STRATEGYQA_FALSE_STRINGS = {"false", "no"}


def is_mcq_question(question: str) -> bool:
    """Detect the GPQA-style 4-choice MCQ marker added by experiments/hf_datasets.py.

    Module-level twin of ``APIBranchGenerator._is_mcq_question`` so callers outside this
    class (e.g. ``experiments/controllers.py``) can check MCQ-ness without needing an
    ``APIBranchGenerator`` instance. Purely additive: only questions built by the
    corrected GPQA loader contain this exact instruction line, so this never changes
    behavior for GSM8K/MATH-500/any other dataset's prompts.
    """
    return _MCQ_MARKER in (question or "")


def sanitize_mcq_final_answer(answer: str | None, question: str) -> str | None:
    """For MCQ-detected questions, only ever allow a single A/B/C/D letter (or ``None``)
    to be committed as a controller-level final answer.

    Rejects: numeric values (a GSM8K/MATH-style side-channel mechanism -- opcheck,
    decomp-eq, PAL/code-execution, unit-tracking, outcome-verifier rerank, targeted
    retry -- overriding the incumbent answer with a numeric result for what is actually
    a lettered multiple-choice question; observed for a real Cohere GPQA-MCQ example,
    see docs/MCQ_CONTROLLER_FINAL_ANSWER_GUARD_20260705.md) and the ``model_step_missing``
    sentinel (exact or as a substring). Non-MCQ questions are returned unchanged --
    this must never alter GSM8K/MATH-500 numeric answer behavior.
    """
    if not is_mcq_question(question):
        return answer
    if answer is None:
        return None
    s = str(answer).strip()
    if not s:
        return None
    if _MODEL_STEP_MISSING_SENTINEL in s:
        return None
    if s.upper() in ("A", "B", "C", "D"):
        return s.upper()
    return None


def gpqa_terminal_finalization_fallback_eligible(
    *, prediction: str | None, question: str, provider: str, model: str,
) -> bool:
    """Strict guardrail gate for the one-shot GPQA terminal finalization fallback.

    True only when ALL of: the normal method already exhausted its budget without a
    *valid* MCQ answer, the question is GPQA-MCQ (via the same is_mcq_question marker
    used everywhere else), the provider is fireworks, and the model is
    deepseek-v4-pro. Never eligible for GSM8K/MATH-500/StrategyQA, non-Fireworks
    providers, non-deepseek-v4-pro Fireworks models, or when a valid answer already
    exists.

    "Valid" is checked with the same A/B/C/D-only rule sanitize_mcq_final_answer uses,
    NOT a bare `is not None` check -- the base controller's own no-answer state surfaces
    as an empty string ("", from _resolve_expand_answer's MCQ branch returning "" on
    parse failure), not Python None, confirmed by direct inspection of a real failing
    row's result_metadata["selected_final_answer_raw"] == "". A naive `is not None`
    check would treat that empty string as "already answered" and silently never fire
    the fallback -- this was a real bug caught by a live smoke test, not a hypothetical
    (see nonconverging_examples_diagnosis.md). An ordinary wrong-but-parseable A/B/C/D
    answer is still correctly treated as ineligible (this is a completion mechanism for
    missing answers, not a re-answering mechanism).
    """
    if prediction is not None and str(prediction).strip().upper() in ("A", "B", "C", "D"):
        return False
    if not is_mcq_question(question):
        return False
    if provider != "fireworks":
        return False
    if "deepseek-v4-pro" not in str(model or "").lower():
        return False
    return True


def build_gpqa_terminal_finalization_prompt(question: str, last_response_text: str) -> str:
    """Construct the one-shot forced-choice finalization prompt.

    Only a short tail of last_response_text is included (enough to recall which
    hypothesis was in progress, not a re-invitation to keep exploring) -- this is
    deliberately NOT a request for new reasoning, only a forced terminal choice from
    what has already been produced.

    The strict output instruction is stated FIRST (primacy) and repeated LAST (recency),
    with the question/reasoning context sandwiched in between -- an earlier version put
    the instruction only at the end, after the full question and up to 4000 chars of
    reasoning; DeepSeek-v4-pro reliably re-engaged in fresh restatement/exploration before
    ever reaching that trailing instruction, exhausting even a 128-token budget on prose
    with no JSON at all (confirmed live, twice, not hypothetical -- see
    nonconverging_examples_diagnosis.md). Short reasoning tail + leading instruction is an
    attempt to reduce that re-engagement pull, not a proven fix by itself -- the token
    budget is also raised in the same change (see run_gpqa_terminal_finalization_fallback)
    since prompt position alone was not confirmed sufficient in isolation.
    """
    trimmed = (last_response_text or "")[-600:]
    return (
        "STOP. Do not analyze, explain, or continue reasoning. Output ONLY this exact "
        'JSON shape, nothing before or after it: {"answer": "A"}\n'
        "The answer value must be exactly one character: A, B, or C, or D.\n\n"
        f"Question:\n{question}\n\n"
        f"Your last few words of prior reasoning (for your own recall only, do not repeat "
        f"or continue it): ...{trimmed}\n\n"
        "Now output ONLY the JSON object with your final choice. No words before or after it."
    )


def parse_gpqa_terminal_finalization_response(raw_text: str) -> str | None:
    """Strict single-tier parse for the terminal finalization response.

    Deliberately does NOT fall back to prose/marker mining (unlike the normal
    _resolve_expand_answer chain) -- this call's entire point is a forced, minimal,
    unambiguous JSON answer field. Malformed JSON, a missing/non-string/multi-character
    "answer" field, or any value other than a bare A/B/C/D letter is rejected to None.
    """
    if not raw_text:
        return None
    data = APIBranchGenerator._safe_json(raw_text)
    if not isinstance(data, dict):
        return None
    ans = data.get("answer")
    if not isinstance(ans, str):
        return None
    s = ans.strip().upper()
    if s in ("A", "B", "C", "D"):
        return s
    return None


def is_strategyqa_question(question: str) -> bool:
    """Detect the StrategyQA True/False marker added by
    scripts/build_strategyqa_problems_file.py::build_strategyqa_prompt(). Module-level twin of
    ``APIBranchGenerator._is_strategyqa_question``, mirroring ``is_mcq_question`` above. Purely
    additive: only StrategyQA prompts contain this exact instruction line, so this never changes
    behavior for GSM8K/MATH-500/GPQA prompts.
    """
    return _STRATEGYQA_MARKER in (question or "")


def strict_normalize_strategyqa_answer(answer: str | None) -> str | None:
    """Question-independent core of sanitize_strategyqa_final_answer(): maps true/false/yes/no
    (case-insensitive, optional surrounding whitespace/trailing period) to canonical "True"/
    "False", and declines (returns None) for everything else -- notably bare digits ("0"/"1"),
    unlike the more lenient scripts/build_strategyqa_problems_file.normalize_boolean_answer.
    Reused by scripts/postprocess_oracle_tree_gold_labels.py for candidate-answer scoring, where
    there is no `question` text available to marker-detect StrategyQA-ness (the caller already
    knows the dataset from the row itself).
    """
    if answer is None:
        return None
    s = str(answer).strip()
    if not s:
        return None
    if _MODEL_STEP_MISSING_SENTINEL in s:
        return None
    s_norm = s.rstrip(".").strip().lower()
    if s_norm in _STRATEGYQA_TRUE_STRINGS:
        return "True"
    if s_norm in _STRATEGYQA_FALSE_STRINGS:
        return "False"
    return None


def sanitize_strategyqa_final_answer(answer: str | None, question: str) -> str | None:
    """For StrategyQA-detected questions, only ever allow the canonical strings ``"True"`` or
    ``"False"`` (or ``None``) to be committed as a candidate/final answer.

    Root-cause fix for the real pilot bug (pilot_fireworks_deepseekv4pro_strategyqa,
    2026-07-16): Fireworks DeepSeek-v4-pro returned raw numeric strings (``"1.0"``, ``"2006"``,
    ``"8"``) in the ``final_answer``/``answer`` JSON keys for StrategyQA boolean questions, and
    nothing in the extraction path validated them before they were committed as
    ``branch.predicted_answer`` -- unlike GPQA, which already had an analogous MCQ-only guard
    (``sanitize_mcq_final_answer``) for exactly this class of bug. Deliberately narrower than
    scripts/build_strategyqa_problems_file.py::normalize_boolean_answer (no bare digits, no
    single-letter y/n) -- see the module-level docstring on ``_STRATEGYQA_TRUE_STRINGS`` for why.
    Non-StrategyQA questions are returned unchanged -- this must never alter GSM8K/MATH-
    500/GPQA answer behavior.
    """
    if not is_strategyqa_question(question):
        return answer
    return strict_normalize_strategyqa_answer(answer)


def extract_strategyqa_explicit_final_answer(text: str | None) -> str | None:
    """Conservative StrategyQA-only fallback for explicit final-answer text.

    Trusted, in order:
      1. Lines with an explicit final-answer marker.
      2. A whole-response boolean surface form (and nothing else).

    Deliberately does NOT mine arbitrary reasoning text for yes/no mentions.
    """
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    found: set[str] = set()
    for pat in _STRATEGYQA_FINAL_BOOL_MARKER_PATTERNS:
        for m in pat.finditer(raw):
            normalized = strict_normalize_strategyqa_answer(m.group(1))
            if normalized:
                found.add(normalized)
    if len(found) == 1:
        return next(iter(found))
    if len(found) > 1:
        return None
    return strict_normalize_strategyqa_answer(raw)


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
        if self.provider == "vertex_gemini":
            default_base_url = "vertex_ai://aiplatform.googleapis.com"
        elif self.provider == "gemini":
            # Deprecated: Gemini Developer API (generativelanguage.googleapis.com + API key).
            # Use provider="vertex_gemini" for Vertex AI via google-genai + ADC.
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
        elif self.provider in {"cloudrift_ai", "cloudrift"}:
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
        is_mcq = self._is_mcq_question(question)
        is_strategyqa = self._is_strategyqa_question(question)
        answer, extraction_source = self._resolve_expand_answer(
            text,
            merged,
            expand_prompt_variant=self.expand_prompt_variant,
            is_mcq=is_mcq,
            is_strategyqa=is_strategyqa,
        )
        if is_mcq:
            # Post-filter, same pattern as the StrategyQA guard below: _resolve_expand_answer's
            # PRIMARY json-key loop returns merged["final_answer"]/["answer"] verbatim before
            # ever consulting `is_mcq` -- a stray non-letter value placed there directly by the
            # model (not merely a fallback-path numeric-mining artifact) would previously sail
            # through unvalidated. sanitize_mcq_final_answer is the same guard already applied
            # at the experiments/controllers.py layer for a real observed Cohere GPQA incident
            # (docs/MCQ_CONTROLLER_FINAL_ANSWER_GUARD_20260705.md); wiring it here closes the
            # analogous gap in this generator, which never called it.
            sanitized = sanitize_mcq_final_answer(answer, question)
            if sanitized is None and answer:
                extraction_source = "api_parse_failed_no_answer_mcq"
            answer = sanitized or ""
        if is_strategyqa:
            sanitized = sanitize_strategyqa_final_answer(answer, question)
            if sanitized is None and answer:
                extraction_source = "api_parse_failed_no_answer_strategyqa"
            answer = sanitized or ""
        self.last_expand_answer_extraction_source = extraction_source
        confidence = self._clip01(self._to_float(merged.get("confidence", branch.score)))

        if step:
            branch.steps.append(step)
        elif action != "final":
            branch.steps.append(_MODEL_STEP_MISSING_SENTINEL)

        branch.score = 0.6 * branch.score + 0.4 * confidence

        if action == "final" or answer:
            branch.is_done = True
            # MCQ guard: _extract_last_number mines the last number out of `step`
            # (built for GSM8K/MATH free-form reasoning) with no awareness of MCQ --
            # applying it to an MCQ question can surface a numeric value (e.g. an
            # intermediate quantity mentioned in reasoning) as if it were the model's
            # A/B/C/D answer even though `_resolve_expand_answer` already safely declined
            # to extract one. Never mine a digit tail for MCQ questions; see
            # docs/MCQ_CONTROLLER_FINAL_ANSWER_GUARD_20260705.md. Same rationale for
            # StrategyQA: a numeric value mined from reasoning text must never be committed
            # as a True/False answer (real pilot bug, see sanitize_strategyqa_final_answer).
            if is_mcq or is_strategyqa:
                digit_tail = ""
            else:
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
            # Safe request/response diagnostics (no prompt/secret duplication beyond what's
            # already in prompt_text/response_text above): token usage, retry count, and
            # finish_reason -- populated for azure_openai and the OpenAI-compatible providers
            # (Fireworks/Cloudrift), empty dict for providers that don't set last_request_meta.
            "request_meta": dict(self.last_request_meta) if self.last_request_meta else {},
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
        maybe_answer, verify_extraction_source = self._resolve_verify_answer(
            text,
            merged,
            is_mcq=self._is_mcq_question(question),
            is_strategyqa=self._is_strategyqa_question(question),
        )
        if self._is_mcq_question(question):
            sanitized = sanitize_mcq_final_answer(maybe_answer, question)
            if sanitized is None and maybe_answer:
                verify_extraction_source = "api_parse_failed_no_answer_mcq"
            maybe_answer = sanitized or ""
        if self._is_strategyqa_question(question):
            sanitized = sanitize_strategyqa_final_answer(maybe_answer, question)
            if sanitized is None and maybe_answer:
                verify_extraction_source = "api_parse_failed_no_answer_strategyqa"
            maybe_answer = sanitized or ""
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
        if self.provider == "vertex_gemini":
            return self._call_vertex_gemini_api(prompt)
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

        effective_max_tokens = self._gpqa_mcq_effective_max_tokens_floor(
            prompt, self.max_tokens, provider=self.provider, model=self.model
        )
        payload = {
            "model": self.model,  # Azure deployment name, e.g. "gpt-4.1-mini"
            "messages": [
                {"role": "system", "content": "Return only valid JSON matching the requested schema."},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": effective_max_tokens,  # gpt-4.1-mini supports max_tokens (not max_completion_tokens)
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
                    finish_reason = ""
                    try:
                        finish_reason = str(((body.get("choices") or [{}])[0]).get("finish_reason") or "")
                    except Exception:
                        finish_reason = ""
                    message = {}
                    try:
                        message = (((body.get("choices") or [{}])[0]).get("message") or {})
                    except Exception:
                        message = {}
                    self.last_request_meta = {
                        "attempts": int(attempt + 1),
                        "input_tokens": int(prompt_tokens),
                        "output_tokens": int(completion_tokens),
                        "max_output_tokens_requested": int(self.max_tokens),
                        "max_output_tokens_effective": int(effective_max_tokens),
                        "response_finish_reason": finish_reason,
                        "response_message_content_present": bool(isinstance(message.get("content"), str) and message.get("content").strip()),
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

    @staticmethod
    def _cloudrift_extra_payload(provider: str, model: str) -> dict:
        """Return provider-specific extra payload keys for Cloudrift/Qwen3.

        Qwen3 defaults to thinking mode, which consumes the entire token budget
        on reasoning and returns content=None.  Disable it for short-answer tasks.
        Only applied when provider is cloudrift/cloudrift_ai AND model contains 'qwen'.
        """
        if provider in {"cloudrift", "cloudrift_ai"} and "qwen" in model.lower():
            return {"chat_template_kwargs": {"enable_thinking": False}}
        return {}

    @staticmethod
    def _response_format_extra_payload(provider: str) -> dict:
        """Explicitly request strict JSON mode where it has been verified to work.

        Confirmed 2026-07-16 (outputs/fireworks_cloudrift_dataset_audit_20260716_20260716T162753Z/
        json_mode_compat_results.json): Fireworks accepts and honors
        response_format={"type":"json_object"} for deepseek-v4-pro and gpt-oss-120b (both
        returned syntactically valid JSON with it set). This is strictly additive to the
        existing system-prompt instruction ("Return only valid JSON..."), never a replacement
        for it -- the plain-text fallback extraction path in _resolve_expand_answer /
        _resolve_verify_answer is unchanged and still engages if a model ignores this field.

        Deliberately provider-scoped, not blanket-enabled for every OpenAI-compatible
        provider: Cloudrift/Cloudrift AI's current model set has not been re-verified against
        this field (the provider was down at verification time), and other unverified
        OpenAI-compatible providers should not silently receive a parameter that might be
        rejected or ignored in an unverified way.
        """
        if provider == "fireworks":
            return {"response_format": {"type": "json_object"}}
        return {}

    @staticmethod
    def _gpqa_mcq_effective_max_tokens_floor(prompt: str, requested: int, *, provider: str = "", model: str = "") -> int:
        """Output-token floor for GPQA-MCQ (4-choice) prompts.

        Root cause (confirmed 2026-07-17 by direct inspection of raw response_text in
        outputs/interpretable_cross_model_completion_batch2_20260716T225834Z/cells/
        {azure_openai,fireworks}__.../gpqa_diamond per_example_records.jsonl, not guessed):
        at the previous 180-token-per-call cap, every failed Azure example showed
        output_tokens=1080 exactly (6 direct-reserve attempts x 180, i.e. every single
        attempt individually truncated), while *successful* Azure examples used up to 1039
        tokens for a single attempt's real reasoning-then-answer JSON -- 180 was simply too
        low for GPQA's longer physics/chemistry reasoning to reach the "answer" field before
        truncation, for a real, non-trivial fraction of questions. Fireworks DeepSeek-v4-pro
        showed the same truncation-before-JSON-answer pattern even more severely.

        2048 is chosen with real margin above the observed 1039-token successful-completion
        high-water mark for Azure gpt-4.1-mini, confirmed sufficient by a live 20-example
        smoke test (outputs/interpretable_gpqa_parser_fix_smoke_20260717T133608Z/azure/):
        39/40 rows valid at 2048 (97.5%).

        Fireworks DeepSeek-v4-pro needs a materially higher floor than Azure: the same smoke
        test at 2048 still showed 2/4 examples exhausting all 6 direct-reserve attempts x
        2048 tokens (output_tokens=12288 exactly) without ever reaching a final answer --
        direct inspection of one such raw response_text showed genuine, unfinished
        chain-of-thought reasoning (not a formatting problem), consistent with this model's
        already-documented tendency (see the StrategyQA floor below) to ignore a tight token
        budget and keep reasoning in prose. 4096 (double Azure's floor) is used for this
        provider/model until/unless evidence from the full completion run says otherwise.

        Scoped to GPQA-MCQ prompts only (detected via is_mcq_question, the same GPQA-only
        marker already used for MCQ answer sanitization) -- GSM8K/MATH-500/StrategyQA prompts
        are completely unaffected.
        """
        if not is_mcq_question(prompt):
            return max(1, int(requested))
        floor = 2048
        if provider == "fireworks" and "deepseek-v4-pro" in str(model).lower():
            floor = 4096
        return max(int(requested), floor)

    @classmethod
    def _openai_compatible_effective_max_tokens(cls, provider: str, model: str, prompt: str, requested: int) -> int:
        """Provider/model/dataset-specific output-token floor for unstable JSON completion paths.

        Fireworks DeepSeek-v4-pro on StrategyQA was observed on Friday, July 17, 2026 to
        repeatedly ignore strict JSON mode, emit long prose, and hit the output cap before ever
        reaching a final boolean answer. The matched-budget protocol counts logical calls rather
        than completion-token equality, so this is treated as a provider reliability floor, not an
        additional reasoning step. Scope stays deliberately narrow to avoid perturbing unrelated
        providers, models, or datasets.
        """
        effective = max(1, int(requested))
        if provider == "fireworks" and "deepseek-v4-pro" in str(model).lower() and is_strategyqa_question(prompt):
            effective = max(effective, 1024)
        effective = max(effective, cls._gpqa_mcq_effective_max_tokens_floor(prompt, effective, provider=provider, model=model))
        return effective

    def _call_openai_compatible_chat_api(
        self,
        prompt: str,
        *,
        override_max_tokens: int | None = None,
        override_temperature: float | None = None,
        override_system_prompt: str | None = None,
    ) -> str:
        """Generic OpenAI-compatible /v1/chat/completions call (Fireworks, Cloudrift AI, etc.).

        The override_* kwargs exist solely for the one-shot GPQA terminal finalization
        fallback (see run_gpqa_terminal_finalization_fallback below), which needs a short,
        deterministic, differently-worded call -- everything else (retry/error handling,
        token accounting, response_format hardening) is reused unchanged.
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if override_max_tokens is not None:
            effective_max_tokens = int(override_max_tokens)
        else:
            effective_max_tokens = self._openai_compatible_effective_max_tokens(
                self.provider,
                self.model,
                prompt,
                self.max_tokens,
            )
        system_prompt = override_system_prompt or "Return only valid JSON matching the requested schema."
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature if override_temperature is None else override_temperature,
            "max_tokens": effective_max_tokens,
            **self._cloudrift_extra_payload(self.provider, self.model),
            **self._response_format_extra_payload(self.provider),
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
                    finish_reason = ""
                    try:
                        finish_reason = str(((body.get("choices") or [{}])[0]).get("finish_reason") or "")
                    except Exception:
                        finish_reason = ""
                    message = {}
                    try:
                        message = (((body.get("choices") or [{}])[0]).get("message") or {})
                    except Exception:
                        message = {}
                    self.last_request_meta = {
                        "attempts": int(attempt + 1),
                        "input_tokens": int(prompt_tokens),
                        "output_tokens": int(completion_tokens),
                        "max_output_tokens_requested": int(self.max_tokens),
                        "max_output_tokens_effective": int(effective_max_tokens),
                        "response_finish_reason": finish_reason,
                        "response_message_content_present": bool(isinstance(message.get("content"), str) and message.get("content").strip()),
                        "response_message_reasoning_present": bool(isinstance(message.get("reasoning"), str) and message.get("reasoning").strip()),
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
            # Safety fallback: if thinking mode was not suppressed (e.g. non-Qwen
            # Cloudrift model or future provider), surface reasoning as a last resort.
            reasoning = message.get("reasoning")
            if isinstance(reasoning, str) and reasoning.strip():
                return reasoning
        raise RuntimeError(f"{self.provider} API returned no text output.")

    def run_gpqa_terminal_finalization_fallback(self, question: str) -> tuple[str | None, dict[str, Any]]:
        """Exactly one bounded terminal-finalization call for a method that exhausted its
        normal budget without a valid GPQA-MCQ answer.

        Callers MUST have already confirmed gpqa_terminal_finalization_fallback_eligible(...)
        -- this method does not re-check eligibility, only performs the call, so it can be
        unit-tested independently of the gate. Callers MUST call this at most once per
        method-run (no internal retry loop here by design -- "one-shot" is enforced by the
        caller invoking it exactly once, not by internal state).

        Uses self.last_response_text (the most recent raw response from this generator
        instance's own normal reasoning, set by every expand() call) as the "reasoning
        already produced" context -- no new reasoning budget, no new branch, exactly one
        additional API call charged and logged.
        """
        prompt = build_gpqa_terminal_finalization_prompt(question, self.last_response_text or "")
        text = self._call_openai_compatible_chat_api(
            prompt,
            # 64, then 128 tokens were tried first and both confirmed (live, twice) still
            # insufficient: DeepSeek-v4-pro reliably ignores the "no reasoning" instruction
            # and starts narrating a fresh restatement of the question, hitting
            # finish_reason="length" before ever emitting the JSON answer, at both budgets.
            # 256 -- combined with the prompt redesign in
            # build_gpqa_terminal_finalization_prompt (leading instruction, short reasoning
            # tail) -- is still an order of magnitude below the normal reasoning budget
            # (2048-4096), i.e. clearly a short/bounded terminal step, not a second full
            # reasoning phase, even though it exceeds the user's original 32-128 suggestion.
            override_max_tokens=256,
            override_temperature=0.0,
            override_system_prompt='Return only valid JSON with a single "answer" field. No other text.',
        )
        answer = parse_gpqa_terminal_finalization_response(text)
        meta = {
            "terminal_finalization_fallback_used": True,
            "terminal_finalization_response_text": text,
            "terminal_finalization_parsed_answer": answer,
            "terminal_finalization_request_meta": dict(self.last_request_meta) if self.last_request_meta else {},
        }
        return answer, meta

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

    def _call_vertex_gemini_api(self, prompt: str) -> str:
        """Vertex AI Gemini via google-genai SDK (ADC, no API key, not Developer API)."""
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "google-genai package required for vertex_gemini provider. "
                "Install with: pip install 'google-genai>=2.6'"
            ) from exc

        project = os.environ.get("VERTEX_GEMINI_PROJECT", "hypnotic-surge-492117-c4")
        location = os.environ.get("VERTEX_GEMINI_LOCATION", "us-central1")
        # gemini-2.5-flash often needs >220 tokens for complete JSON on math/MCQ prompts.
        effective_max_tokens = max(int(self.max_tokens), 1024)
        client = getattr(self, "_vertex_genai_client", None)
        if client is None:
            client = genai.Client(vertexai=True, project=project, location=location)
            self._vertex_genai_client = client

        retry_attempts = self.retry_max_attempts
        last_exc: Exception | None = None
        for attempt in range(retry_attempts):
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.temperature,
                        max_output_tokens=effective_max_tokens,
                        response_mime_type="application/json",
                    ),
                )
                text = response.text
                if not isinstance(text, str) or not text.strip():
                    raise RuntimeError("Vertex Gemini API returned no text output.")
                usage = getattr(response, "usage_metadata", None)
                in_tok = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
                out_tok = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
                self.total_input_tokens += in_tok
                self.total_output_tokens += out_tok
                self.total_api_calls += 1
                self.total_retry_attempts += int(attempt)
                self.last_request_meta = {
                    "attempts": int(attempt + 1),
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "api_endpoint_type": "vertex_ai",
                    "vertex_project": project,
                    "vertex_location": location,
                    "model": self.model,
                    "max_output_tokens_requested": int(self.max_tokens),
                    "max_output_tokens_effective": int(effective_max_tokens),
                }
                return text
            except Exception as exc:  # pragma: no cover - network path
                last_exc = exc
                err_text = f"{type(exc).__name__}: {exc}"
                retryable = any(
                    token in err_text
                    for token in ("429", "408", "500", "502", "503", "504", "RESOURCE_EXHAUSTED", "UNAVAILABLE")
                )
                if retryable and attempt < retry_attempts - 1:
                    delay = self._compute_retry_delay_seconds(attempt)
                    self._log_retry_attempt(
                        provider="vertex_gemini",
                        attempt_number=attempt + 1,
                        max_attempts=retry_attempts,
                        reason=err_text[:200],
                        wait_seconds=delay,
                    )
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"Vertex Gemini API request failed: {err_text[:500]}") from exc
        raise RuntimeError(f"Vertex Gemini API request failed after retries: {last_exc}")  # pragma: no cover

    def _call_gemini_api(self, prompt: str) -> str:
        """Gemini Developer API (generativelanguage.googleapis.com). Prefer vertex_gemini."""
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
        cleaned, _applied = APIBranchGenerator.normalize_markdown_fenced_json(text)
        return cleaned

    @staticmethod
    def normalize_markdown_fenced_json(text: str) -> tuple[str, bool]:
        """Strip outer markdown code fences for JSON parsing; preserve inner content."""
        raw = str(text or "")
        t = raw.strip()
        m = _JSON_FENCE_FULL.match(t)
        if m:
            return m.group(1).strip(), True
        emb = _JSON_FENCE_EMBED.search(t)
        if emb:
            return emb.group(1).strip(), True
        return t, False

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
    def _extract_truncated_json_field(text: str, field: str) -> str | None:
        """Best-effort recovery of a single scalar field from a response that looks
        like it started as a JSON object but never closed (e.g. cut off by an output-token
        budget partway through a later, verbose field such as ``step``). Only recovers
        ``field`` when its own value is itself complete -- this does not guess at or
        repair a field whose own value was truncated, and it does not mine numbers from
        free-form prose (``_plain_text_answer_fallback`` already deliberately declines
        that for truncated-JSON-looking input; this is a narrower, JSON-key-aware
        complement, not a replacement).

        Two forms of "complete" are recognized:
          - quoted string: opening and matching, non-escaped closing quote both present.
          - bare JSON number (e.g. Gemini sometimes emits ``"answer": 42`` unquoted):
            only recovered when immediately followed (after optional whitespace) by a
            ``,`` or ``}``, since that is the only way to know the digit run itself
            wasn't the part cut off by truncation.
        """
        if not text:
            return None
        t = str(text).strip()
        if not t.startswith("{"):
            return None
        string_pattern = re.compile(r'"' + re.escape(field) + r'"\s*:\s*"((?:[^"\\]|\\.)*)"')
        m = string_pattern.search(t)
        if m:
            return m.group(1)
        numeric_pattern = re.compile(
            r'"' + re.escape(field) + r'"\s*:\s*(-?\d+(?:\.\d+)?)\s*(?=[,}])'
        )
        m = numeric_pattern.search(t)
        if m:
            return m.group(1)
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
    def _resolve_strategyqa_json_answer(merged: dict[str, Any], keys: tuple[str, ...]) -> tuple[str, str]:
        for k in keys:
            normalized = strict_normalize_strategyqa_answer(merged.get(k))
            if normalized:
                tag = "api_json_final_answer" if k == "final_answer" else "api_json_answer"
                return normalized, tag
        return "", ""

    @staticmethod
    def _stringify_scalar_answer_value(v: object) -> str:
        if v is None or isinstance(v, (dict, list)):
            return ""
        if isinstance(v, bool):
            return "true" if v else "false"
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
        # Unwrap a ```json ... ``` (or bare ```) code fence before the JSON-object guard below,
        # so a fenced JSON blob is recognized the same way an unfenced one already is. Without
        # this, a fenced-but-otherwise-well-formed JSON object (e.g. the model wrapped its
        # response in ```json even though it did not set action=="final"/a populated answer
        # field) slips past the `startswith("{")` guard and falls into the generic
        # extract_final_answer last-number mining below, which then reads across the *whole*
        # JSON blob and can pick up an unrelated trailing field's numeric value (observed: a
        # `"confidence": 1` field being mined as the answer instead of the real number stated in
        # the model's own "step" reasoning text). See same_model_sc_preflight investigation,
        # 2026-07-24: reproduced deterministically for azure_openai/gpt-4.1-mini.
        fence_match = _JSON_FENCE_FULL.match(t)
        unfenced = fence_match.group(1).strip() if fence_match else t
        stripped = unfenced.lstrip()
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

    @staticmethod
    def _extract_mcq_letter_answer(text: str) -> str | None:
        """Conservative, multiple-choice-only fallback for free-text (non-JSON) model
        output: recovers a single, unambiguous final-answer letter (A/B/C/D) ONLY when
        it is explicitly tied to a final-answer marker (``Final answer: X``,
        ``Answer: X``, ``The answer is X``, ``\\boxed{X}``).

        Deliberately does NOT treat a bare trailing letter (e.g. the last line/character
        of a truncated response) as a safe signal -- offline diagnosis of real CloudRift
        GPQA responses found a case where a response was truncated mid-sentence right
        after discussing an option comparatively (e.g. "...this statement is correct for
        spin-1/2 systems.\\nB"), leaving a bare trailing "B" that was mid-thought, not a
        deliberate final answer -- and the gold answer was a different letter. Only
        explicit final-answer markers are trusted. Also does NOT mine a letter from
        restated option labels (e.g. an ``A) ...`` line reciting the choices) or from any
        other prose location, and returns ``None`` -- decline to recover -- the moment
        more than one distinct letter is asserted this way, since that is a
        conflicting/ambiguous signal, not a safe recovery. This exists specifically so
        numeric answer-mining (built for GSM8K/MATH free-response tasks) is never applied
        to MCQ questions, where it would silently extract a wrong-typed, unrelated number.
        """
        if not text:
            return None
        t = str(text)
        found: set[str] = set()
        for pat in _MCQ_FINAL_LETTER_MARKER_PATTERNS:
            for m in pat.finditer(t):
                found.add(m.group(1).upper())
        if len(found) == 1:
            return next(iter(found))
        return None

    @classmethod
    def _resolve_expand_answer(
        cls,
        raw_text: str,
        merged: dict[str, Any],
        *,
        expand_prompt_variant: str = "default",
        is_mcq: bool = False,
        is_strategyqa: bool = False,
    ) -> tuple[str, str]:
        """Return (answer, extraction_source_tag) for expand() (gold-free)."""
        if is_strategyqa:
            answer, tag = cls._resolve_strategyqa_json_answer(merged, _EXPAND_ANSWER_KEYS)
            if answer:
                return answer, tag
            if not merged:
                for k in _EXPAND_ANSWER_KEYS:
                    recovered = cls._extract_truncated_json_field(raw_text, k)
                    normalized = strict_normalize_strategyqa_answer(recovered)
                    if normalized:
                        tag = "api_json_final_answer" if k == "final_answer" else "api_json_answer"
                        return normalized, f"{tag}_truncated_recovery"
            explicit = extract_strategyqa_explicit_final_answer(raw_text)
            if explicit:
                return explicit, "api_strategyqa_explicit_final_answer"
            return "", "api_parse_failed_no_answer_strategyqa"
        for k in _EXPAND_ANSWER_KEYS:
            s = cls._stringify_scalar_answer_value(merged.get(k))
            if s:
                tag = "api_json_final_answer" if k == "final_answer" else "api_json_answer"
                return s, tag
        if not merged:
            for k in _EXPAND_ANSWER_KEYS:
                recovered = cls._extract_truncated_json_field(raw_text, k)
                if recovered is None:
                    continue
                recovered = recovered.strip()
                if recovered and recovered != _MODEL_STEP_MISSING_SENTINEL:
                    tag = "api_json_final_answer" if k == "final_answer" else "api_json_answer"
                    return recovered, f"{tag}_truncated_recovery"
        if is_mcq:
            # MCQ questions never have a numeric answer -- the generic numeric-mining
            # fallbacks below (built for GSM8K/MATH) must never run here, since they
            # would extract an unrelated number as if it were a multiple-choice letter.
            letter = cls._extract_mcq_letter_answer(raw_text)
            if letter:
                return letter, "api_mcq_letter_fallback"
            return "", "api_parse_failed_no_answer_mcq"
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
    def _resolve_verify_answer(
        cls, raw_text: str, merged: dict[str, Any], *, is_mcq: bool = False, is_strategyqa: bool = False
    ) -> tuple[str, str]:
        if is_strategyqa:
            answer, tag = cls._resolve_strategyqa_json_answer(merged, _VERIFY_ANSWER_KEYS)
            if answer:
                return answer, tag
            if not merged:
                for k in _VERIFY_ANSWER_KEYS:
                    recovered = cls._extract_truncated_json_field(raw_text, k)
                    normalized = strict_normalize_strategyqa_answer(recovered)
                    if normalized:
                        tag = "api_json_final_answer" if k == "final_answer" else "api_json_answer"
                        return normalized, f"{tag}_truncated_recovery"
            explicit = extract_strategyqa_explicit_final_answer(raw_text)
            if explicit:
                return explicit, "api_strategyqa_explicit_final_answer"
            return "", "api_parse_failed_no_answer_strategyqa"
        for k in _VERIFY_ANSWER_KEYS:
            s = cls._stringify_scalar_answer_value(merged.get(k))
            if s:
                tag = "api_json_final_answer" if k == "final_answer" else "api_json_answer"
                return s, tag
        if not merged:
            for k in _VERIFY_ANSWER_KEYS:
                recovered = cls._extract_truncated_json_field(raw_text, k)
                if recovered is None:
                    continue
                recovered = recovered.strip()
                if recovered and recovered != _MODEL_STEP_MISSING_SENTINEL:
                    tag = "api_json_final_answer" if k == "final_answer" else "api_json_answer"
                    return recovered, f"{tag}_truncated_recovery"
        if is_mcq:
            letter = cls._extract_mcq_letter_answer(raw_text)
            if letter:
                return letter, "api_mcq_letter_fallback"
            return "", "api_parse_failed_no_answer_mcq"
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

    @staticmethod
    def _is_mcq_question(question: str) -> bool:
        """Detect the GPQA-style 4-choice MCQ marker added by experiments/hf_datasets.py.

        Purely additive: only questions built by the corrected GPQA loader contain this
        exact instruction line, so this never changes behavior for GSM8K/MATH-500/any
        other dataset's prompts. Delegates to the module-level ``is_mcq_question`` so
        this class and external callers (e.g. ``experiments/controllers.py``) share one
        definition.
        """
        return is_mcq_question(question)

    @staticmethod
    def _is_strategyqa_question(question: str) -> bool:
        """Detect the StrategyQA True/False marker. Delegates to the module-level
        ``is_strategyqa_question`` so this class and external callers share one definition
        (same pattern as ``_is_mcq_question`` above)."""
        return is_strategyqa_question(question)

    def _expand_prompt(self, question: str, branch: BranchState) -> str:
        prior = "\n".join(f"- {s}" for s in branch.steps[-3:]) or "(none)"
        is_vertex_gemini = self.provider == "vertex_gemini"
        is_cloudrift = self.provider == "cloudrift"
        if self._is_strategyqa_question(question):
            return (
                "You are answering a True/False question. Respond with ONLY a single valid JSON object. "
                "Return strict JSON with keys in this exact order: action, answer, step, confidence. "
                "Strongly prefer action='final' as soon as you can form a best guess. "
                "action must be 'continue' or 'final'. "
                "answer must be a JSON boolean: true or false. Never use a number, never use a quoted string, and never leave answer ambiguous. "
                "step must be at most one short sentence and should briefly justify the answer. "
                "If you do not return JSON, then the FIRST non-empty line must be exactly "
                "'Final answer: True' or 'Final answer: False', followed by at most one short sentence. "
                "confidence is 0..1.\n\n"
                f"Question:\n{question}\n\n"
                f"Current partial reasoning:\n{prior}\n"
            )
        if self._is_mcq_question(question):
            if is_vertex_gemini:
                return (
                    "You are answering a 4-choice multiple-choice question. Continue reasoning for "
                    "ONE short step or finish with a final choice. If you can already determine the "
                    "correct option from the question and prior reasoning, use action='final' and put "
                    "the single letter (A, B, C, or D) in answer (do not defer unnecessarily). "
                    "Return strict JSON with keys in this exact order: action, answer, step, confidence "
                    "-- write answer BEFORE step so it is never lost if step runs long. "
                    "action must be 'continue' or 'final'. answer should be empty unless final; when "
                    "final, answer must be exactly one of A, B, C, D. "
                    "step must be at most one short sentence (no more than ~25 words) -- a brief note, "
                    "never a full derivation. confidence is 0..1.\n\n"
                    f"Question:\n{question}\n\n"
                    f"Current partial reasoning:\n{prior}\n"
                )
            if is_cloudrift:
                # CloudRift/Qwen was observed reverting to unbounded free-text chain-of-
                # thought on GPQA-MCQ, ignoring the JSON contract entirely (see
                # docs/CLOUDRIFT_GPQA_PARSE_DIAGNOSIS_AND_FIX_20260705.md) -- tightened,
                # more directive variant: explicitly forbids prose outside the JSON
                # object, biases toward an immediate final letter, and caps step length
                # more aggressively than the default MCQ prompt.
                return (
                    "You are answering a 4-choice multiple-choice question. "
                    "Respond with ONLY a single JSON object and nothing else -- no prose, no "
                    "explanation, no derivation outside the JSON object. Do not write out a "
                    "full step-by-step derivation in free text. "
                    "Strongly prefer action='final' with your single best-guess letter in answer "
                    "as soon as you can determine it, even if uncertain -- do not defer to "
                    "'continue' unless truly necessary. "
                    "Return strict JSON with keys in this exact order: action, answer, step, "
                    "confidence -- write answer BEFORE step. "
                    "action must be 'continue' or 'final'. answer should be empty unless final; "
                    "when final, answer must be exactly one capital letter: A, B, C, or D -- "
                    "nothing else. "
                    "step must be at most one short sentence (no more than ~15 words) -- a brief "
                    "note only, never a full derivation. confidence is 0..1.\n\n"
                    f"Question:\n{question}\n\n"
                    f"Current partial reasoning:\n{prior}\n"
                )
            return (
                "You are answering a 4-choice multiple-choice question. Continue reasoning for "
                "ONE short step or finish with a final choice. If you can already determine the "
                "correct option from the question and prior reasoning, use action='final' and put "
                "the single letter (A, B, C, or D) in answer (do not defer unnecessarily). "
                "Return strict JSON with keys: action, step, answer, confidence. "
                "action must be 'continue' or 'final'. answer should be empty unless final; when "
                "final, answer must be exactly one of A, B, C, D. confidence is 0..1.\n\n"
                f"Question:\n{question}\n\n"
                f"Current partial reasoning:\n{prior}\n"
            )
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
        if is_vertex_gemini:
            return (
                "You are solving a GSM8K math word problem. Continue reasoning for ONE short step or finish with a final numeric answer. "
                "If you can already determine the final numeric result from the question and prior reasoning, use action='final' and put that number in answer (do not defer unnecessarily). "
                "Return strict JSON with keys in this exact order: action, answer, step, confidence "
                "-- write answer BEFORE step so it is never lost if step runs long. "
                "action must be 'continue' or 'final'. answer should be empty unless final. "
                "step must be at most one short sentence (no more than ~25 words) -- a brief note, "
                "never a full derivation or LaTeX-heavy restatement of the solution. confidence is 0..1.\n\n"
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
        if self._is_strategyqa_question(question):
            return (
                "You are a lightweight verifier for a True/False question. "
                "Return ONLY valid JSON with keys: confidence, candidate_answer, rationale_short. "
                "confidence must be 0..1. "
                "candidate_answer may be empty if unknown; otherwise it must be exactly true or false as a JSON boolean. "
                "If you do not return JSON, then the FIRST non-empty line must be exactly "
                "'Final answer: True' or 'Final answer: False', followed by at most one short sentence. "
                "rationale_short must be one short sentence.\n\n"
                f"Question:\n{question}\n\n"
                f"Reasoning path:\n{prior}\n\n"
                f"Current predicted answer (if any): {branch.predicted_answer or ''}\n"
            )
        if self._is_mcq_question(question):
            return (
                "You are a lightweight verifier for a 4-choice multiple-choice question. Assess if "
                "the current reasoning path seems correct. "
                "Return strict JSON with keys: confidence (0..1), candidate_answer, rationale_short. "
                "candidate_answer may be empty if unknown, otherwise must be exactly one of A, B, C, D.\n\n"
                f"Question:\n{question}\n\n"
                f"Reasoning path:\n{prior}\n\n"
                f"Current predicted answer (if any): {branch.predicted_answer or ''}\n"
            )
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
