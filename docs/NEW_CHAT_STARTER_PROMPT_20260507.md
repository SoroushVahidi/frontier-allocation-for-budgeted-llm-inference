# New chat starter prompt (2026-05-07)

Copy everything inside the fence into a fresh ChatGPT / assistant session after opening the repo at **`research-next-wt`**, branch **`research-next-frontier-iteration-2`**.

```text
You are helping on the research codebase “frontier-allocation-for-budgeted-llm-inference” (worktree: research-next-wt).

FIRST READ (in order):
1) docs/CURRENT_RESEARCH_HANDOFF_20260507.md  — single source of truth for May 2026 frontier-iteration-2 status.
2) docs/CURRENT_ARTIFACTS_INDEX_20260507.md — which output folders are canonical vs local-heavy.
3) docs/CLAIMS.md — safe vs unsafe claims.
4) START_HERE_CURRENT.md — short entry pointer.

Current best method (internal):
- direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal
- shorthand: PAL + retry / guarded PAL

External baselines:
- external_l1_max (primary headline comparator)
- external_tale_prompt_budgeting
- external_s1_budget_forcing
- external_l1_exact is diagnostic/fairness—not the main headline comparator.

Empirical headline (300-case paired): PAL+retry 252/300 vs external_l1_max 244/300; gap +8 cases (~+2.67 pp); McNemar p≈0.32; bootstrap CI crosses zero → directional only, NOT statistically decisive superiority.

30-case 4-way pilot (small slice): PAL 17/30; external_l1_max 21/30; external_tale_prompt_budgeting 20/30; external_s1_budget_forcing 20/30 — interpret only with bundle manifests.

247-ID 4-way collection (see failure_collection_summary.json in latest collect bundle): PAL competitive vs single-method externals; outcome tables include **34** external-only (PAL wrong, ≥1 external correct) on complete rows—see **CURRENT_RESEARCH_HANDOFF**.

Current bottleneck:
- Track B: present-not-selected / commitment / overlay / histogram / surfacing consistency is PRIORITY for external-win failures.
- Track A/TRCE: gold-absent discovery still important but not majority of newest preferred external-win mining.

Next implementation candidate:
- Track B design contract (overlay/commitment consistency) — MUST pass offline fixtures + guardrail replay BEFORE code changes.
- Implementation is NOT done yet.

No-go rules:
- Do NOT claim statistical superiority over external_l1_max from current evidence.
- Do NOT run paid/API batches unless user explicitly approves a capped plan with call estimates.
- Do NOT implement new selectors until offline replay criteria pass.
- Do NOT use gold labels as runtime rules.
- Do NOT repeat failed directions: naive global max_answer_group_support, DR-heavy finals, broad rate/ratio gates, selector-isolated logging that consumes search budget, blind PAL-exec priority.

Artifacts (paths relative to repo root):
- outputs/pal_retry_300case_analysis_20260506/report.md
- outputs/failure_case_corpus_20260507/ (pattern seeds + corpus)
- outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/ (if present locally: mining + present-not-selected replay + Track B design contract)

Tests/fixtures:
- tests/test_build_failure_case_corpus.py
- tests/fixtures/present_not_selected_replay/ + tests/test_present_not_selected_replay_fixtures.py (if present)

WARNING — stale comparisons:
- Do NOT infer current-best results from strict_f3-only or strict_gate1_cap_k6-only older harnesses; always anchor to PAL+retry ID above unless explicitly comparing historical methods.

Reply by summarizing current bottleneck + recommended next offline step, then ask what the user wants you to execute (still no API unless approved).
```
