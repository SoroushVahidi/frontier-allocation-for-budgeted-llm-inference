# Oracle-distilled controller behavioral metrics protocol (evaluation-readiness, pre-HPC)

## Status

This protocol is an **evaluation-readiness upgrade** for the existing oracle-distilled stop-vs-act pipeline.
It does **not** run heavy oracle-label generation and does **not** claim oracle-phase wins.

## 1) Why ACT/STOP classification accuracy is insufficient

Classification metrics (accuracy/AUC/Brier) answer: *"did the student match a label?"*
They do **not** directly answer: *"did the controller make good budgeted decisions?"*

Two controllers can have similar classifier scores while inducing very different policy behavior:

- one spends ACT where ACT is genuinely beneficial,
- another spends ACT in harmful states and misses beneficial ACT opportunities.

Therefore, classifier metrics remain useful diagnostics, but are **not headline policy criteria**.

## 2) Why matched ACT-rate / compute-rate evaluation is required

The stop-vs-act controller is a **budget policy**, so quality must be judged under comparable spend.
Unmatched ACT-rate (or compute-rate) confounds interpretation:

- acting less can look safer but may hide harmful premature STOP,
- acting more can inflate some gains but waste budget.

Operational rule:

1. Keep matched-coverage controls already in place.
2. Require ACT-rate (and observed compute-rate when available) side-by-side.
3. Interpret policy-quality deltas under matched-rate tolerance whenever possible.

## 3) First-class behavioral metrics added now

Using per-state ACT-vs-STOP utility gap (`oracle_action_gap`), add:

- **BAR**: Beneficial ACT rate
- **HAR**: Harmful ACT rate
- **HPSR**: Harmful premature STOP rate
- **BSR**: Beneficial STOP rate
- **Oracle-action regret**

These are **policy-behavior metrics**, not auxiliary curiosities.

## 4) Primitive quantity / estimator contract

Primary primitive in this upgrade:

- `oracle_action_gap := utility(ACT) - utility(STOP)` (per state)

State typing with optional neutral band `epsilon` (`behavior_neutral_gap_band`):

- beneficial-ACT state: `oracle_action_gap > +epsilon`
- harmful-ACT state: `oracle_action_gap < -epsilon`
- neutral/ambiguous: `|oracle_action_gap| <= epsilon`

Policy decision is student ACT/STOP at the configured threshold.

Metric formulas over **eligible eval rows** (rows where `oracle_action_gap` exists):

- `BAR = P(student=ACT and gap>+epsilon)`
- `HAR = P(student=ACT and gap<-epsilon)`
- `HPSR = P(student=STOP and gap>+epsilon)`
- `BSR = P(student=STOP and gap<-epsilon)`
- `OracleActionRegret = mean( gap if STOP on beneficial state; -gap if ACT on harmful state; else 0 )`

Availability rule:

- If `oracle_action_gap` is missing for all eval rows, emit `available=false` with explicit reason.
- If partially missing, emit metrics on eligible rows and report eligible/missing counts.

## 5) Interpretation guide

Directional interpretation:

- higher **BAR** is better,
- lower **HAR** is better,
- lower **HPSR** is better,
- higher **BSR** is better,
- lower **oracle-action regret** is better.

Joint interpretation rule:

- BAR increases are not sufficient if HAR or HPSR also rise materially.
- Prefer policies that improve BAR/BSR while reducing HAR/HPSR and regret under matched-rate views.

## 6) Safe vs unsafe claims before real oracle-phase outputs

### Safe after this implementation

- The pipeline now emits policy-behavior metrics when required primitives are present.
- The pipeline explicitly reports behavioral metric availability/missingness.
- Matched-control comparison outputs can now include BAR/HAR/HPSR/BSR/regret fields.

### Unsafe before real oracle-phase outputs

- Claiming distilled policy superiority from mock/proxy-only runs.
- Claiming oracle-phase improvement without validated pilot labels.
- Claiming final model promotion solely from classifier metrics.

## 7) Operational output requirements (current pipeline)

Per run summary (`oracle_distilled_student_summary.json`) now includes:

- `evaluation.controller_behavior.available`
- `evaluation.controller_behavior.primitive_quantity`
- `evaluation.controller_behavior.beneficial_act_rate_bar`
- `evaluation.controller_behavior.harmful_act_rate_har`
- `evaluation.controller_behavior.harmful_premature_stop_rate_hpsr`
- `evaluation.controller_behavior.beneficial_stop_rate_bsr`
- `evaluation.controller_behavior.oracle_action_regret`
- `evaluation.controller_behavior.eligible_rows / missing_rows`

Comparison summary now carries run-level behavior fields and behavior availability coverage.

## 8) Non-claim guardrails

- Keep existing non-claim/provenance markers active.
- Treat readiness smoke tests as structural validation only.
- Promote to substantive oracle claims only after validated pilot outputs exist.
