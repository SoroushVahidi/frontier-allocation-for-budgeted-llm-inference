from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CallAccounting:
    actual_cohere_calls_completed_rows: int
    actual_cohere_calls_run_level: int
    effective_call_cap: int | None
    global_cap_reached: bool
    cap_error_count: int
    completed_rows: int
    incomplete_rows: int
    call_accounting_source: list[str]
    call_accounting_warning: str


def compute_call_accounting(
    *,
    completed_rows: int,
    total_rows: int,
    cap_error_count: int,
    per_case_calls_sum: int,
    budget_snapshot: dict[str, int | None],
    inferred_from_errors: int | None = None,
) -> CallAccounting:
    budget = budget_snapshot.get("budget")
    consumed = int(budget_snapshot.get("consumed") or 0)
    global_cap_reached = bool(budget is not None and consumed >= int(budget))
    run_level = consumed
    sources = ["per_case_counter", "global_runner_counter"]
    warning = ""
    if global_cap_reached:
        sources.append("cap_enforcer")
    if inferred_from_errors is not None and inferred_from_errors > run_level:
        run_level = int(inferred_from_errors)
        sources.append("inferred_from_errors")

    if run_level != per_case_calls_sum:
        warning = (
            "run-level logical call consumption differs from sum of completed-row "
            "per-case counters; use actual_cohere_calls_run_level for cost/cap interpretation."
        )

    return CallAccounting(
        actual_cohere_calls_completed_rows=int(per_case_calls_sum),
        actual_cohere_calls_run_level=int(run_level),
        effective_call_cap=(int(budget) if budget is not None else None),
        global_cap_reached=global_cap_reached,
        cap_error_count=int(cap_error_count),
        completed_rows=int(completed_rows),
        incomplete_rows=int(max(0, total_rows - completed_rows)),
        call_accounting_source=sources,
        call_accounting_warning=warning,
    )
