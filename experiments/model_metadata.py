"""Canonical (provider, exact_model, underlying_model_family) metadata and per-token pricing.

Single source of truth so that oracle-tree generation (scripts/oracle_tree_generator_v2.py)
and any downstream analysis/conditioning code (provider-conditioning, LOPO, feature-table
builders) agree on model identity. Two Fireworks models (deepseek-v4-pro, gpt-oss-120b) must
never collapse under provider=="fireworks" alone -- that is the concrete bug this module fixes.

Pricing is per-provider/per-model, not a single flat placeholder. Every entry records its
pricing_source so callers can distinguish a verified rate from a fallback guess. Verified rates
below were checked via web search on 2026-07-16 (see
outputs/learned_budget_allocator_next_mining_plan_20260716_20260716T164314Z/cost_estimates.json
for the sourcing detail); they are NOT re-derived from provider APIs at runtime -- if a
provider changes its public pricing, this table must be updated by hand.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    input_usd_per_million: float
    output_usd_per_million: float
    source: str  # "verified_web_search_20260716" | "fallback_placeholder_unverified"


# Conservative fallback: the repo's original flat placeholder rate, expressed per-million.
# Used ONLY for (provider, model) pairs not present in PRICING_TABLE below -- never silently
# assumed to be accurate, always tagged with source="fallback_placeholder_unverified" so
# downstream cost totals can be filtered/flagged.
_FALLBACK_PRICING = ModelPricing(
    input_usd_per_million=3.00,
    output_usd_per_million=15.00,
    source="fallback_placeholder_unverified",
)

# Keyed by (provider, exact model string exactly as passed to APIBranchGenerator/--model).
PRICING_TABLE: dict[tuple[str, str], ModelPricing] = {
    ("cohere", "command-r-plus-08-2024"): ModelPricing(2.50, 10.00, "verified_web_search_20260716"),
    ("azure_openai", "gpt-4.1-mini"): ModelPricing(0.40, 1.60, "verified_web_search_20260716"),
    ("vertex_gemini", "gemini-2.5-flash"): ModelPricing(0.30, 2.50, "verified_web_search_20260716"),
    ("fireworks", "accounts/fireworks/models/deepseek-v4-pro"): ModelPricing(1.74, 3.48, "verified_web_search_20260716"),
    ("fireworks", "accounts/fireworks/models/gpt-oss-120b"): ModelPricing(0.15, 0.60, "verified_web_search_20260716"),
}

# Canonical underlying_model_family derivation. Deliberately a plain function (not inferred
# from the model string at call time in a fragile way) so new models are an explicit,
# reviewable one-line addition, not a regex guess.
_MODEL_FAMILY_TABLE: dict[tuple[str, str], str] = {
    ("cohere", "command-r-plus-08-2024"): "command-r-plus",
    ("azure_openai", "gpt-4.1-mini"): "gpt-4.1-mini",
    ("vertex_gemini", "gemini-2.5-flash"): "gemini-2.5-flash",
    ("fireworks", "accounts/fireworks/models/deepseek-v4-pro"): "deepseek-v4",
    ("fireworks", "accounts/fireworks/models/gpt-oss-120b"): "gpt-oss",
    ("cloudrift", "Qwen/Qwen3.6-35B-A3B-FP8"): "qwen3.6-35b",
    ("cloudrift_ai", "Qwen/Qwen3.6-35B-A3B-FP8"): "qwen3.6-35b",
}


def get_pricing(provider: str, model: str) -> ModelPricing:
    """Return the pricing entry for (provider, model), falling back to a clearly-tagged
    conservative placeholder for anything not explicitly verified."""
    return PRICING_TABLE.get((provider, model), _FALLBACK_PRICING)


def call_cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int) -> tuple[float, str]:
    """Return (cost_usd, pricing_source) for one API call's real token counts."""
    pricing = get_pricing(provider, model)
    cost = (input_tokens / 1_000_000.0) * pricing.input_usd_per_million + \
           (output_tokens / 1_000_000.0) * pricing.output_usd_per_million
    return cost, pricing.source


def derive_underlying_model_family(provider: str, model: str) -> str:
    """Canonical (provider, model) -> underlying_model_family mapping.

    Falls back to the raw model string (lowercased, path-stripped) for any pair not yet
    registered above, so a brand-new model still gets a usable (if unrefined) family label
    instead of silently colliding with something else under the same provider.
    """
    known = _MODEL_FAMILY_TABLE.get((provider, model))
    if known:
        return known
    tail = model.rsplit("/", 1)[-1]
    return tail.lower()


def group_key(row: dict) -> tuple[str, str, str]:
    """Canonical grouping key for provider-conditioning / LOPO / feature-table analysis.

    Use this instead of grouping by row["provider"] alone -- that collapses distinct model
    families that happen to share a provider (e.g. fireworks/deepseek-v4-pro and
    fireworks/gpt-oss-120b), which silently pools their behavioral signal together.
    """
    provider = str(row.get("provider", ""))
    model = str(row.get("model", ""))
    family = row.get("underlying_model_family") or derive_underlying_model_family(provider, model)
    return (provider, model, str(family))


def add_model_family_column(df):
    """Pandas helper: add an 'underlying_model_family' column to a DataFrame that has
    'provider' and 'model' columns, without mutating the input DataFrame in place."""
    out = df.copy()
    out["underlying_model_family"] = [
        derive_underlying_model_family(str(p), str(m))
        for p, m in zip(out["provider"], out["model"])
    ]
    return out
