# Conservative trace-support selector report

- selector: `conservative_trace_support_selector_v1`
- input: `outputs/selector_evidence_trace_recovery_20260501T023200Z/candidate_trace_enriched.jsonl`
- cases: 50

## Scope and safety framing

- This is a **present-not-selected recovery benchmark**.
- It **does not measure runtime break risk**.
- **No API calls were made** (no Cohere/OpenAI/Anthropic usage).
- Decision-time selector logic does **not** use `gold_answer`, `oracle_selector_answer`, `oracle_selector_would_fix`, or any `evaluation_only` field.

## Result summary

- total overrides: 0
- fixes: 0
- breaks: 0
- net fixes minus breaks: 0
- selector accuracy: 0.0
- current incumbent accuracy: 0.0
- oracle ceiling on package: 0.92
- recoverable trace-terminal cases: 46
- recoveries among gold-terminal cases: 0
- gold-terminal failures not chosen: 46
- aggregate-only cases: 4

## Conclusion

`conservative_trace_support_selector_v1` is a valid deterministic no-API baseline, but it is too conservative on this recovery benchmark. It made zero overrides and recovered zero of the 46 trace-terminal recoverable cases. This supports moving next to an outcome-verifier selector rather than relying on support/source/trace features alone.
