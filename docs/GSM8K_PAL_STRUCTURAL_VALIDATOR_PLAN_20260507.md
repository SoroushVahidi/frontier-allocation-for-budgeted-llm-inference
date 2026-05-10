# GSM8K / PAL structural validator — offline-first plan (2026-05-07)

**Worktree:** `research-next-wt`  
**Scope:** Planning only — **no validator implementation in this step.**  
**Related repos (ideas):** `SoroushVahidi/combinatorial-opt-agent` — lightweight validators, NLP→structure cues, metadata separation from answers.

---

## A. Motivation from current frontier project failures

1. **Present-not-selected cohort (~23 cases)** — Failures are often **not** “PAL never ran” but **surface/channel mismatch**: overlay or tie-break signals point at a consistent numeric peer while **executable PAL stdout** or another branch wins selection. Histogram-only fixes regress guardrails; **structural evidence** that the final numeric **uses** quantities and operations implied by the prompt is missing from automatic diagnostics.

2. **Gold-absent / preferred-external-win slice (~11 cases)** — Without oracle labels at inference, the system needs **quantity/relation discovery** proxies: which mentioned numbers were carried through, whether rate/total/temporal cues appear in reasoning/code, whether the proposed answer type fits the question (“how many”, “how much longer”, “difference”, etc.).

3. **Track B** — The commitment gate improves **overlay vs stdout consistency** under narrow preconditions but is **not proven** to lift live accuracy without paired-run artifacts; a **validator layer** can attach **per-candidate structural scores** independent of gate firing, improving offline diagnosis and future gating without claiming solver correctness.

---

## B. Combinatorial Opt Agent ideas to borrow

From **`formulation/verify.py`** (conceptual pattern):

- Validators are **lightweight**, **never raise**; they return **lists** of errors and warnings (and optionally structured tags).
- Split concerns: **`verify_problem_schema`**, **`verify_formulation_structure`**, **`verify_lp_consistency`**, **`verify_python_syntax`** — **structural checks before** any solver-backed or heavy verification.

From **`tools/nlp4lp_downstream_utility.py`** (pattern):

- **Numeric mention extraction**, **type/role/slot grounding**, **cue words**, **operator tags**, and **validation/repair** hooks — adapted here as **GSM8K-specific cues** (not LP formulation).

From **`KNOWN_ISSUES.md`**:

- Structural validation is **useful**; **solver-backed** or **oracle** validation is **restricted** — this plan **does not** claim LP/MIP-style soundness; abstain from overclaiming repair guarantees.

From **`app.py`** (UX principle):

- **Validation metadata is surfaced separately** from answer generation — mirror in frontier code: validator output is **telemetry / sidecar**, not a silent rewrite of `final_answer`.

**Operational borrow:**

- **Never-raise** + **list-return** diagnostics.
- **Structural-first** pipeline stage.
- **Metadata attached** to each candidate artifact (branch, PAL stdout, JSON answer, overlay prior).
- Policy default: **abstention / downweight signals**, **not** automatic override of selection.

---

## C. Proposed validator API

Single entry point (pure Python, **no network**, **no gold** in parameters):

```python
def validate_gsm8k_candidate(
    problem_text: str,
    candidate_answer: str | None,
    *,
    candidate_trace: str | None = None,
    candidate_code: str | None = None,
    source_family: str | None = None,
) -> dict[str, Any]:
    ...
```

**Required keys in the returned dict** (stable schema for logging):

| Field | Type | Meaning |
|-------|------|---------|
| `errors` | `list[str]` | Hard structural failures (e.g. unparsable answer when required). |
| `warnings` | `list[str]` | Soft gaps (missing cues, weak coverage). |
| `quantity_mentions` | `list[dict]` | Extracted numerics from problem (+ optional roles): raw span, normalized value, source (`digit` / `word`). |
| `quantity_coverage` | `float \| None` | Heuristic fraction of salient quantities referenced in trace/code/answer channel (0–1). |
| `unused_salient_quantities` | `list[str]` | Mention IDs or normalized values not echoed in reasoning/code path. |
| `operation_cues_required` | `list[str]` | Cues inferred from problem (e.g. `rate`, `difference`, `total`). |
| `operation_cues_found` | `list[str]` | Cues detected in trace/code. |
| `target_question_type` | `str` | Coarse label: `count`, `difference`, `duration`, `rate`, `money`, `fraction`, `unknown`, … |
| `target_type_match` | `bool \| None` | Whether answer surface looks compatible with target type (heuristic). |
| `code_syntax_ok` | `bool \| None` | `None` if no code; else AST/token check result. |
| `exec_ok` | `bool \| None` | Only if executor result supplied out-of-band into an extended API later; **initially always `None`**. |
| `structural_score` | `float` | Bounded score (e.g. 0–1) combining coverage + cue match − penalties. |
| `abstain_reasons` | `list[str]` | Why the validator refuses to strongly endorse/downrank (sparse text, ambiguous target type, etc.). |

**Explicit non-goals for v0:** compute correctness vs gold; call LLM; modify frontier expansion budget.

---

## D. Initial checks to implement (v0)

Ordered roughly by dependency:

1. **Python syntax / code availability** — If `candidate_code` present: `ast.parse` or safe tokenizer; on failure → `errors` entry, `code_syntax_ok=False`.

2. **Numeric extraction (problem + trace)** — Digits + **written English numbers** (bounded lexicon) from `problem_text`; repeat for `candidate_trace` / printed stdout cues.

3. **Quantity coverage** — Map salient quantities to occurrences in trace/code (string normalization, tolerance for floats); compute `quantity_coverage` + `unused_salient_quantities`.

4. **Target-type detection** — Lightweight pattern sets for GSM8K-like questions (regex + keyword families): “how many”, “how much more”, “per day”, “each”, “remaining”, “difference”, “ratio”, “percent”.

5. **Rate / per / every cue check** — Detect problem cues; verify analogous operators or divisions appear in trace/code (`/`, `per`, step text).

6. **Temporal / state-change cue check** — “before/after”, “then”, “another”, “still”, multi-step story cues vs single-shot answers.

7. **Difference / comparison cue check** — “more than”, “less than”, “longer”, “heavier”; flag if answer channel looks like a raw count without comparison logic.

8. **Total / aggregation cue check** — “in total”, “altogether”, “combined”, “each … total”.

9. **Unit / type compatibility heuristic** — Money vs pure count vs time (conservative; warnings only).

Each check contributes **warnings** or **abstain_reasons**, not exceptions.

---

## E. Offline evaluation plan

**Datasets (already in project artifacts / CSVs):**

| Cohort | Purpose |
|--------|---------|
| **23 present-not-selected** targets | Does the validator assign **worse** `structural_score` / **more** warnings to the **chosen wrong** surface than to **overlay-aligned** or tie-break peers when those alternatives exist in logged metadata? |
| **11 gold-absent preferred-external-win** | Same comparison **without** gold at inference — use logged alternatives only. |
| **188 guardrail correct** (both PAL + external correct band) | **False alarm rate**: warnings should stay **low** on accepted-good rows. |

**Metrics:**

- **Separation:** distribution of `structural_score` for chosen vs best structural alternative (paired deltas).
- **Calibration:** precision/recall **not** vs gold — vs **human-readable failure tags** where available (mechanism labels in replay tables).

**Tooling:** batch script reading existing JSONL/CSV rows; **no API**.

---

## F. Acceptance criteria

1. **No API** in validator core or batch evaluation driver.
2. **No runtime selection use** in v0 — metadata only (logging, offline reports).
3. **Separation:** On present-not-selected, validator ranks **wrong PAL stdout** **below** at least one **gold-aligned alternative** in **> chance** fraction of cases where alternatives are logged (target: justify with binomial CI in eval memo).
4. **Guardrail false positives:** Warning rate on **188** correct guardrails below an agreed threshold (e.g. `< 20%` strong warnings — **tuned after prototype**).
5. **No gold / eval fields** inside **`validate_gsm8k_candidate`** — gold allowed **only** in offline evaluation scripts that compare validator output post hoc.

---

## G. Tests to write first

1. **Synthetic GSM8K-like prompts** per cue family (rate, temporal, difference, total) with stub trace/code/answer — assert stable `target_question_type`, cue lists, and non-crashing behavior.

2. **Archived failure fixtures** — Reuse `tests/fixtures/present_not_selected_replay/*.json` **without** importing gold into the validator function; tests may compare validator output to **fixture annotations** outside the validator.

3. **Never-raises** — Property-style test: random empty/garbage inputs → dict always returned, no exceptions.

4. **No-gold-input** — Signature inspection / static assert that `validate_gsm8k_candidate` does not accept `gold_answer`.

---

## H. Relationship to Track A and Track B

- **Track B (commitment gate):** Validator metadata can **later** inform when to **trust** overlay/tie-break commitment vs stdout (e.g. high structural support for tie-break group). Does **not** replace the gate in v0.

- **Track A / TRCE-style retries:** **`warnings` / `abstain_reasons`** can trigger **structured retry** prompts or routing in a future iteration — v0 **does not** wire into controllers.

---

## I. Whether API is needed now

**No.** Extraction and cue checks are local string/AST operations; evaluation uses archived rows.

---

## J. Exact next implementation query (for a follow-up session)

Implement **`experiments/gsm8k_structural_validate.py`** (name TBD) with:

- **`validate_gsm8k_candidate`** as in §C.
- Private helpers: `_extract_quantities`, `_classify_target_type`, `_scan_operation_cues`, `_score_coverage`, `_check_code_syntax`.
- **`tests/test_gsm8k_structural_validate.py`** — synthetics + never-raise + fixture smoke.
- **`scripts/eval_gsm8k_structural_validator_offline.py`** (optional) — read cohort CSVs/JSONL, emit **`validator_eval_summary.json`** — **no controller hooks**.

**Do not** call frontier controllers, **do not** change `final_answer` selection, **do not** commit raw outputs.

---

## Push prerequisite note

Commit **`bc693b8`** (“Track B: opt-in commitment gate and evaluator skip”) was pushed to **`origin/research-next-frontier-iteration-2`** before this planning doc was added; **this document is local-only until separately committed.**
