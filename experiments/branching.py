"""Branch state and branch operations for the lightweight pilot experiment."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import random
import re
import time
from typing import Any, Optional
from urllib import error, request

from experiments.code_sandbox import run_restricted_python


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
        branch.steps.append(f"step_{branch.depth + 1}")
        drift = self.rng.uniform(-0.05, 0.08)
        branch.score = min(1.0, max(0.0, branch.score + drift))

        finish_prob = min(0.95, self.finish_prob_base + 0.1 * branch.depth + 0.25 * branch.latent_quality)
        should_finish = branch.depth >= self.max_depth or self.rng.random() < finish_prob

        if should_finish:
            branch.is_done = True
            is_correct = self.rng.random() < max(0.05, branch.score - self.answer_noise)
            branch.predicted_answer = gold_answer if is_correct else self._make_wrong_answer(gold_answer)

        return BranchActionResult("expand", score_before, branch.score, branch.is_done)

    def verify(self, branch: BranchState, question: str) -> BranchActionResult:  # noqa: ARG002
        score_before = branch.score
        correction = (branch.latent_quality - branch.score) * 0.35
        jitter = self.rng.uniform(-0.03, 0.03)
        branch.score = min(1.0, max(0.0, branch.score + correction + jitter))
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
    ) -> None:
        self.provider = provider.strip().lower()
        self.api_key = api_key
        if self.provider == "gemini":
            default_base_url = "https://generativelanguage.googleapis.com/v1beta"
        elif self.provider == "groq":
            default_base_url = "https://api.groq.com/openai/v1"
        else:
            default_base_url = "https://api.openai.com/v1"
        self.base_url = (base_url or default_base_url).rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

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
        data = self._safe_json(text)

        action = str(data.get("action", "continue")).strip().lower()
        step = str(data.get("step", ""))[:500]
        answer = str(data.get("answer", "")).strip()
        confidence = self._clip01(self._to_float(data.get("confidence", branch.score)))

        if step:
            branch.steps.append(step)
        elif action != "final":
            branch.steps.append("model_step_missing")

        branch.score = 0.6 * branch.score + 0.4 * confidence

        if action == "final" or answer:
            branch.is_done = True
            branch.predicted_answer = answer or self._extract_last_number(step)

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
        data = self._safe_json(text)
        confidence = self._clip01(self._to_float(data.get("confidence", branch.score)))
        maybe_answer = str(data.get("candidate_answer", "")).strip()

        branch.score = 0.5 * branch.score + 0.5 * confidence
        if maybe_answer and branch.predicted_answer is None:
            branch.predicted_answer = maybe_answer
        return BranchActionResult("verify", score_before, branch.score, branch.is_done)

    @staticmethod
    def prune(branch: BranchState) -> BranchActionResult:
        score_before = branch.score
        branch.is_pruned = True
        return BranchActionResult("prune", score_before, branch.score, branch.is_done)

    def _call_api(self, payload: dict, prompt: str) -> str:
        if self.provider == "gemini":
            return self._call_gemini_api(prompt)
        if self.provider == "groq":
            return self._call_groq_chat_api(prompt)
        return self._call_responses_api(payload)

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
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - network path
            err_body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Gemini API HTTPError {exc.code}: {err_body[:500]}") from exc
        except Exception as exc:  # pragma: no cover - network path
            raise RuntimeError(f"Gemini API request failed: {exc}") from exc

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
    def _safe_json(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
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
        return (
            "You are solving a GSM8K math word problem. Continue reasoning for ONE short step or finish with a final numeric answer. "
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
