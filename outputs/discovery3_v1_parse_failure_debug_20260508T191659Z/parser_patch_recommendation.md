# Parser patch recommendation

- FINAL_ANSWER support status: existing pilot parser already supports strict `FINAL_ANSWER: <number>`.
- Existing parser missed because model emitted `final_answer / FINAL_ANSWER: <number>` (non-exact contract).
- Recommended parser change now: none (prefer prompt contract fix first).
- Parser code changed in this step: no.
- Safe future fallback (optional): accept `final_answer / FINAL_ANSWER:` alias via method-agnostic regex if parse failures persist after contract fix.
- Risk: overly permissive parser fallback can increase ambiguous parse acceptance and hide output-contract regressions.
