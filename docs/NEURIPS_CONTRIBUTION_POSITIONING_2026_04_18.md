# NeurIPS contribution positioning (2026-04-18)

## Why this note exists

This note freezes the manuscript-facing contribution so the repository stops drifting between:
- a broad “universally best adaptive compute method” narrative (not supported), and
- a narrower, evidence-backed contribution around fixed-budget hard branch allocation (supported).

It translates current repository evidence into an exact paper claim scope.

---

## 1) Candidate contribution formulations

### Candidate A (too broad)

> We present a generally superior adaptive test-time compute allocator for LLM reasoning.

Status: **reject** (overclaim; not supported by current comparison status).

### Candidate B (narrow but incomplete)

> We study fixed-budget next-step branch allocation and show multistep branch utility is a strong method line.

Status: **acceptable but underspecified** (does not foreground the key diagnostic/oracle-definition contribution).

### Candidate C (recommended canonical formulation)

> We formulate fixed-budget LLM test-time reasoning as a next-step branch-allocation problem and contribute a method-and-analysis framework showing that continuation-centered multistep allocation is a strong baseline, while the decisive unresolved region is a small ambiguity-sensitive near-tie slice where continuation and completion evidence can disagree; in that slice, bounded completion-aware correction should augment (not replace) continuation-based allocation.

Status: **recommended canonical statement**.

### Candidate D (also safe, shorter abstract form)

> The core contribution is not universal dominance, but a defensible fixed-budget branch-allocation framework with strong diagnostics that localize where learned allocation works, where it fails, and why hybrid continuation-plus-bounded-completion targets are needed in close-call states.

Status: **safe alternate wording**.

---

## 2) Final canonical contribution statement (freeze)

Use this as the repository-default contribution statement:

> **This work contributes a narrow, defensible NeurIPS-ready result: a fixed-budget next-step branch-allocation formulation for LLM reasoning, a strong continuation-centered multistep allocation line, and a diagnosis framework that localizes failure to ambiguity-sensitive near-tie disagreement states where bounded completion-aware correction improves target fidelity without justifying global replacement of continuation value.**

---

## 3) Claim levels (explicit discipline)

### A. Claim we can make now safely

1. The repository supports a clear and distinct fixed-budget next-step branch-allocation formulation.
2. Multistep continuation-centered allocation remains the strongest bounded learned line among nearby tested variants.
3. Recent bounded nearby target/control refinements did not produce broad successor wins.
4. Observability + casebook + answer recovery now enable direct semantic adjudication of contested states.
5. Oracle-definition disagreement appears small and concentrated in near-tie states in bounded runs; this supports augment-not-replace target design.

### B. Strongest regime-of-strength claim

> Our method line is strongest in hard ambiguity-sensitive branch-allocation states (especially near-ties), where better target definition and disagreement handling matter more than broad model-class swapping.

### C. Claims we cannot make yet

1. Universal/broad best-overall performance across datasets and baselines.
2. A solved target-definition question across all conditions.
3. A final, robustly dominant learned allocator.
4. Completion-aware targets as global replacement objectives.

### D. Strongest unsafe overreach to avoid

> “Our method is the best overall adaptive compute allocator for LLM reasoning.”

This is not supported by current comparison and safe-claim docs.

---

## 4) Paper-shape map around the frozen contribution

## 4.1 Problem formulation

- Task: under a fixed budget, repeatedly decide which active branch gets the next compute unit.
- Decision object: relative branch utility/allocation priority, not generic “more reasoning helps.”

## 4.2 Why the problem is hard

- Hardness is concentrated in close-call branch states (near ties, small utility gaps).
- Proxy supervision and target mismatch dominate in this region.
- Continuation value and visible completion quality can diverge locally.

## 4.3 What existing methods miss (as framed by this repo)

- Many nearby local target/control tweaks fail to move hardest slices.
- Model-class upgrades alone are insufficient.
- Forced single-objective framing hides disagreement-state pathology.

## 4.4 What our method contributes

- A continuation-centered multistep branch-utility method line that remains strongest in bounded comparisons.
- A bounded hybrid stance: continuation as core, completion-aware evidence only in disagreement slices.

## 4.5 What diagnostics/failure analysis contributes

- Direct branch reasoning and recovered final-answer evidence on contested states.
- Semantic adjudication of method-vs-oracle disagreements instead of proxy-only diagnosis.
- Case-backed localization of objective mismatch in near-tie slices.

## 4.6 Where the method is strongest

- Hard, ambiguity-sensitive allocation states where ranking/allocation fidelity is the main challenge.
- Especially near-tie decision regions where disagreement handling affects quality.

## 4.7 Remaining limitations

- No broad universal dominance evidence.
- Current disagreement evidence is bounded-slice and should not be overgeneralized.
- Full cross-dataset external-baseline closure remains incomplete.

---

## 5) Novelty vs supportive infrastructure

## Novel contribution (paper-center)

1. **Problem framing contribution**: fixed-budget next-step branch-allocation as the central object.
2. **Method contribution (narrow)**: continuation-centered multistep allocation as strongest current line.
3. **Analysis contribution**: observability-enabled semantic disagreement adjudication + oracle-mismatch localization, yielding augment-not-replace hybrid target stance.

## Supportive infrastructure (important but not headline novelty)

- extensive baseline adapters and import validators,
- dataset/manifest/provenance expansion,
- broad experimentation scaffolding,
- additional exploratory target/control families that did not become canonical winners.

These increase credibility, but should not be presented as the main paper novelty.

---

## 6) Evidence checklist backing the frozen contribution

1. **Canonical framing + safe-claim discipline**: current safe claims and canonical positioning notes.
2. **Comparison status**: full comparison note showing competitiveness but not broad universal best.
3. **Recent bounded-pass synthesis**: nearby refinements did not displace multistep-k3.
4. **Oracle-mismatch evidence**: disagreement concentrated and supports augmentation.
5. **Semantic-case evidence**: direct reasoning/final-answer recovery on contested failures.
6. **Current rule docs**: repository already in target-definition consolidation phase.

---

## 7) Abstract/introduction emphasis guidance

Prioritize language like:
- fixed-budget branch-allocation under uncertainty,
- strong but narrow method claim,
- ambiguity-sensitive near-tie regime,
- diagnostics that expose objective mismatch,
- augment-not-replace target conclusion.

De-emphasize language like:
- universal win,
- solved adaptive compute,
- global replacement target claims,
- “just scale/model size” explanations.

A safe abstract skeleton:
1. define fixed-budget next-step branch allocation,
2. present continuation-centered multistep method line,
3. show where it is strong and where failures concentrate,
4. show diagnostics/oracle-mismatch result,
5. conclude with bounded hybrid target stance and limitations.

---

## 8) What the paper should explicitly not claim

Do **not** claim:
- best overall adaptive compute allocator,
- universal cross-benchmark superiority,
- solved ambiguity handling,
- completion-aware replacement as globally superior,
- that support infrastructure itself is the main scientific novelty.

---

## 9) Repository alignment actions implied by this freeze

1. Make this contribution statement canonical in front-door docs.
2. Keep future experiment admission tied to target-definition/disagreement resolution.
3. Keep claim map synchronized with artifacts before manuscript drafting.
4. Gate abstract/introduction wording against this note and `CURRENT_SAFE_CLAIMS.md`.

---

## 10) One-line final recommendation

> **Position the NeurIPS paper as a narrow, high-credibility contribution on fixed-budget hard branch-allocation with strong ambiguity-focused diagnostics and an augment-not-replace hybrid target conclusion—not as a broad universal adaptive-compute win.**
