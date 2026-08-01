"""Provider adapters for true same-model SC (one generation request per sample).

Wraps existing ``APIBranchGenerator`` Azure/Vertex call paths. Live generation is
gated by the caller; this module never enables repair or controllers.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from experiments.frontier_max_support_tiebreak import normalize_answer_group_key
from experiments.model_metadata import get_pricing

REPO = Path(__file__).resolve().parents[1]

CANONICAL_MODELS = {
    "azure_openai": "gpt-4.1-mini",
    "vertex_gemini": "gemini-2.5-flash",
}

ALLOWLISTED_PROVIDERS = frozenset({"azure_openai", "vertex_gemini"})
ALLOWLISTED_DATASETS = frozenset({"openai/gsm8k"})


@dataclass
class SamplingConfig:
    temperature: float = 0.1
    max_output_tokens: int = 220
    timeout_seconds: float = 60.0
    retry_max_attempts: int = 3


@dataclass
class SampleResult:
    sample_index: int
    request_attempted: bool
    http_success: bool
    raw_text: str
    extracted_answer: str | None
    valid_answer: bool
    input_tokens: int = 0
    output_tokens: int = 0
    latency_seconds: float = 0.0
    estimated_cost_usd: float = 0.0
    provider_reported_cost_usd: float | None = None
    billed_cost_usd: float | None = None
    provider_request_id: str | None = None
    error_category: str = ""
    retryable: bool = False
    attempt_index: int = 0
    provider: str = ""
    model_id: str = ""
    error: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GenerationBackend(Protocol):
    def __call__(
        self,
        *,
        provider: str,
        model_id: str,
        prompt: str,
        sampling_config: SamplingConfig,
        sample_index: int,
        request_metadata: dict[str, Any],
    ) -> SampleResult: ...


def _extract_answer(raw_text: str) -> str | None:
    text = (raw_text or "").strip()
    if not text:
        return None
    # Prefer JSON "answer" field when present (matches repo prompt style).
    if "{" in text and "answer" in text:
        try:
            import json
            import re

            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                obj = json.loads(m.group(0))
                if isinstance(obj, dict) and obj.get("answer") not in (None, ""):
                    ans = str(obj["answer"]).strip()
                    return ans or None
        except Exception:
            pass
    from experiments.data import extract_final_answer

    try:
        ans = extract_final_answer(text)
        if ans is not None and str(ans).strip():
            return str(ans).strip()
    except Exception:
        pass
    key = normalize_answer_group_key(text)
    return key or None


def estimate_cost_usd(provider: str, model_id: str, input_tokens: int, output_tokens: int) -> float:
    pricing = get_pricing(provider, model_id)
    in_rate = float(pricing.input_usd_per_million)
    out_rate = float(pricing.output_usd_per_million)
    return (input_tokens / 1_000_000.0) * in_rate + (output_tokens / 1_000_000.0) * out_rate


def _credential_names_present(keys: list[str]) -> tuple[bool, list[str]]:
    missing = [k for k in keys if not os.environ.get(k)]
    env_path = REPO / ".env"
    if missing and env_path.exists():
        text = env_path.read_text(encoding="utf-8", errors="replace")
        # Name presence only — never log values.
        missing = [k for k in missing if f"{k}=" not in text]
    return (len(missing) == 0, missing)


def azure_preflight() -> dict[str, Any]:
    ok, missing = _credential_names_present(
        ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT"]
    )
    model = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or CANONICAL_MODELS["azure_openai"]
    if model != CANONICAL_MODELS["azure_openai"] and os.environ.get("AZURE_OPENAI_DEPLOYMENT"):
        # Deployment name may equal model id for this project.
        pass
    out = {
        "provider": "azure_openai",
        "ready": ok,
        "model_id": CANONICAL_MODELS["azure_openai"],
        "reasons": ([] if ok else [f"credentials_unavailable:{','.join(missing)}"]),
        "generation_calls": 0,
    }
    return out


def vertex_preflight() -> dict[str, Any]:
    reasons: list[str] = []
    try:
        from google import genai  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"sdk_unavailable:{type(exc).__name__}")
    adc = Path.home() / ".config/gcloud/application_default_credentials.json"
    if not (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or adc.exists()):
        reasons.append("credentials_unavailable:ADC")
    proj = os.environ.get("VERTEX_GEMINI_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not proj:
        # Check .env names only
        env_path = REPO / ".env"
        if env_path.exists():
            text = env_path.read_text(encoding="utf-8", errors="replace")
            if "VERTEX_GEMINI_PROJECT=" not in text and "GOOGLE_CLOUD_PROJECT=" not in text:
                reasons.append("project_unavailable")
        else:
            reasons.append("project_unavailable")
    loc = os.environ.get("VERTEX_GEMINI_LOCATION") or "us-central1"
    return {
        "provider": "vertex_gemini",
        "ready": len(reasons) == 0,
        "model_id": CANONICAL_MODELS["vertex_gemini"],
        "location": loc,
        "reasons": reasons,
        "generation_calls": 0,
    }


def _build_generator(provider: str, model_id: str, sampling: SamplingConfig):
    from experiments.branching import APIBranchGenerator

    api_key = ""
    base_url = ""
    if provider == "azure_openai":
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        base_url = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        if not api_key or not base_url:
            # Load from .env into process env without printing
            _load_env_names_only()
            api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
            base_url = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    elif provider == "vertex_gemini":
        _load_env_names_only()
    else:
        raise ValueError(f"unsupported provider {provider}")

    return APIBranchGenerator(
        api_key=api_key or "UNUSED",
        model=model_id,
        temperature=sampling.temperature,
        max_tokens=sampling.max_output_tokens,
        timeout_seconds=int(sampling.timeout_seconds),
        base_url=base_url or "https://unused.invalid",
        provider=provider,
        retry_max_attempts=int(sampling.retry_max_attempts),
    )


def _load_env_names_only() -> None:
    """Load KEY=VALUE from .env into os.environ if missing; never log values."""
    env_path = REPO / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def generate_one_sample_live(
    *,
    provider: str,
    model_id: str,
    prompt: str,
    sampling_config: SamplingConfig,
    sample_index: int,
    request_metadata: dict[str, Any] | None = None,
) -> SampleResult:
    """One paid-capable generation. Caller must enforce live gates before invoking."""
    request_metadata = request_metadata or {}
    if provider not in ALLOWLISTED_PROVIDERS:
        return SampleResult(
            sample_index=sample_index,
            request_attempted=False,
            http_success=False,
            raw_text="",
            extracted_answer=None,
            valid_answer=False,
            error_category="provider_not_allowlisted",
            error=f"provider {provider} not allowlisted",
            provider=provider,
            model_id=model_id,
        )
    if model_id != CANONICAL_MODELS.get(provider):
        return SampleResult(
            sample_index=sample_index,
            request_attempted=False,
            http_success=False,
            raw_text="",
            extracted_answer=None,
            valid_answer=False,
            error_category="model_mismatch",
            error=f"model_id {model_id} != canonical {CANONICAL_MODELS.get(provider)}",
            provider=provider,
            model_id=model_id,
        )

    gen = _build_generator(provider, model_id, sampling_config)
    t0 = time.time()
    try:
        if provider == "azure_openai":
            raw = gen._call_azure_chat_api(prompt)
        elif provider == "vertex_gemini":
            raw = gen._call_vertex_gemini_api(prompt)
        else:
            raise ValueError(provider)
        latency = time.time() - t0
        meta = dict(getattr(gen, "last_request_meta", {}) or {})
        in_tok = int(meta.get("input_tokens") or 0)
        out_tok = int(meta.get("output_tokens") or 0)
        ans = _extract_answer(raw)
        req_id = None
        if isinstance(meta, dict):
            req_id = meta.get("request_id") or meta.get("id")
        if req_id is None:
            req_id = hashlib.sha256(f"{provider}:{sample_index}:{raw[:64]}".encode()).hexdigest()[:16]
        return SampleResult(
            sample_index=sample_index,
            request_attempted=True,
            http_success=True,
            raw_text=raw,
            extracted_answer=ans,
            valid_answer=bool(ans),
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_seconds=latency,
            estimated_cost_usd=estimate_cost_usd(provider, model_id, in_tok, out_tok),
            provider_request_id=str(req_id),
            attempt_index=int(meta.get("attempts") or 1) - 1,
            provider=provider,
            model_id=model_id,
            meta={"request_metadata": request_metadata, "provider_meta": meta},
        )
    except Exception as exc:  # noqa: BLE001
        latency = time.time() - t0
        err = f"{type(exc).__name__}"
        retryable = any(t in str(exc) for t in ("429", "500", "502", "503", "504", "timeout", "Timeout"))
        return SampleResult(
            sample_index=sample_index,
            request_attempted=True,
            http_success=False,
            raw_text="",
            extracted_answer=None,
            valid_answer=False,
            latency_seconds=latency,
            error_category="api_error",
            retryable=retryable,
            error=err,  # type name only — avoid leaking response bodies/secrets
            provider=provider,
            model_id=model_id,
            meta={"request_metadata": request_metadata},
        )


def _normalize_scripted(
    scripted: dict[Any, Any] | None,
) -> dict[tuple[str, str, int], list[SampleResult]]:
    """Accept tuple keys or JSON-friendly 'provider|example_id|sample_index' keys."""
    out: dict[tuple[str, str, int], list[SampleResult]] = {}
    if not scripted:
        return out
    for key, attempts in scripted.items():
        if isinstance(key, str) and "|" in key:
            parts = key.split("|")
            tkey = (parts[0], parts[1], int(parts[2]))
        elif isinstance(key, (tuple, list)) and len(key) == 3:
            tkey = (str(key[0]), str(key[1]), int(key[2]))
        else:
            raise ValueError(f"bad scripted key: {key!r}")
        parsed: list[SampleResult] = []
        for a in attempts:
            if isinstance(a, SampleResult):
                parsed.append(a)
            else:
                parsed.append(
                    SampleResult(
                        sample_index=int(a.get("sample_index", tkey[2])),
                        request_attempted=True,
                        http_success=bool(a.get("http_success", True)),
                        raw_text=str(a.get("raw_text") or ""),
                        extracted_answer=a.get("extracted_answer"),
                        valid_answer=bool(a.get("valid_answer", bool(a.get("extracted_answer")))),
                        input_tokens=int(a.get("input_tokens") or 10),
                        output_tokens=int(a.get("output_tokens") or 5),
                        latency_seconds=float(a.get("latency_seconds") or 0.01),
                        estimated_cost_usd=float(a.get("estimated_cost_usd") or 0.0001),
                        provider_request_id=a.get("provider_request_id"),
                        error_category=str(a.get("error_category") or ""),
                        retryable=bool(a.get("retryable", False)),
                        attempt_index=int(a.get("attempt_index") or 0),
                        error=str(a.get("error") or ""),
                    )
                )
        out[tkey] = parsed
    return out


def make_mock_backend(scripted: dict[Any, Any] | None = None) -> GenerationBackend:
    """Deterministic mock backend. Keyed by (provider, example_id, sample_index) -> attempt list."""

    calls: list[dict[str, Any]] = []
    scripted_norm = _normalize_scripted(scripted)

    def _backend(
        *,
        provider: str,
        model_id: str,
        prompt: str,
        sampling_config: SamplingConfig,
        sample_index: int,
        request_metadata: dict[str, Any],
    ) -> SampleResult:
        example_id = str(request_metadata.get("example_id") or "")
        key = (provider, example_id, sample_index)
        calls.append(
            {
                "provider": provider,
                "model_id": model_id,
                "sample_index": sample_index,
                "example_id": example_id,
                "prompt_len": len(prompt or ""),
            }
        )
        if key in scripted_norm and scripted_norm[key]:
            res = scripted_norm[key].pop(0)
            res.provider = provider
            res.model_id = model_id
            res.sample_index = sample_index
            res.request_attempted = True
            if not res.provider_request_id:
                res.provider_request_id = f"mock-{provider}-{example_id}-{sample_index}-{len(calls)}"
            return res
        ans = str((sum(map(ord, example_id)) + sample_index) % 97)
        raw = f'{{"answer": "{ans}", "step": "mock"}}'
        return SampleResult(
            sample_index=sample_index,
            request_attempted=True,
            http_success=True,
            raw_text=raw,
            extracted_answer=ans,
            valid_answer=True,
            input_tokens=100 + sample_index,
            output_tokens=20 + sample_index,
            latency_seconds=0.01,
            estimated_cost_usd=0.0001,
            provider_request_id=f"mock-{provider}-{example_id}-{sample_index}-{len(calls)}",
            attempt_index=0,
            provider=provider,
            model_id=model_id,
        )

    _backend.calls = calls  # type: ignore[attr-defined]
    return _backend


# Default live backend (must only be used after live gates).
generate_one_sample: GenerationBackend = generate_one_sample_live
