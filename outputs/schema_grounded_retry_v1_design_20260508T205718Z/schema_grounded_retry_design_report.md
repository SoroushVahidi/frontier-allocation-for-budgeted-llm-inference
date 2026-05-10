# Schema-Grounded Retry v1 Design

## Why free-form retry failed
- Free-form retry outputs repeatedly missed strict terminal formatting requirements (`FINAL_ANSWER`), causing pervasive parse failures.
- Even when numeric content existed, responses were ambiguous (multiple numbers/no marker), making safe automatic selection/commit infeasible.
- Retry triggers occurred but commit never fired, so final surface stayed on structural commit path.

## How schema-grounded retry differs
- Replaces unconstrained free-form reasoning with fixed labeled blocks and one numeric terminal field.
- Makes parsing and structural validation deterministic before any commit consideration.
- Separates candidate *generation quality* from commit-policy gating by enforcing machine-readable structure first.

## Proposed fixed schema catalog
### 1) quantity_ledger_schema
- **Trigger:** money/accumulation/multi-quantity totals.
- **Required fields:** SCHEMA_TYPE, TARGET_QUANTITY, GIVEN_QUANTITIES, EQUATIONS, COMPUTATION, FINAL_ANSWER.
- **Example format:** ledger-like givens + compact equations + numeric final line.
- **Verifier checks:** one FINAL_ANSWER, numeric final, non-empty equations/computation.
- **Reject when:** missing block labels, multiple final answers, non-numeric final.

### 2) rate_table_schema
- **Trigger:** explicit rate/unit/time cues.
- **Required fields:** same canonical block set.
- **Example format:** rate rows in GIVEN_QUANTITIES + conversion equation.
- **Verifier checks:** equations present and dimension-consistent structure.
- **Reject when:** no equations or ambiguous final.

### 3) before_after_state_schema
- **Trigger:** sequential update terms (before/after/then/remaining).
- **Required fields:** canonical blocks with state transitions in computation.
- **Example format:** initial state, transitions, final target extraction.
- **Verifier checks:** non-empty computation and one numeric final.
- **Reject when:** missing transitions or conflicting finals.

### 4) ratio_equation_schema
- **Trigger:** ratio/twice/half/as-many patterns.
- **Required fields:** canonical blocks.
- **Example format:** variable ratio equations + solved target.
- **Verifier checks:** equations non-empty, parseable final.
- **Reject when:** no ratio equations or multi-final conflict.

### 5) target_difference_schema
- **Trigger:** asks difference/how many more/less.
- **Required fields:** canonical blocks.
- **Example format:** identify compared quantities + subtraction target equation.
- **Verifier checks:** explicit target quantity and single final.
- **Reject when:** intermediate-only output or missing final marker.

### 6) average_total_count_schema
- **Trigger:** average/mean/score target cues.
- **Required fields:** canonical blocks.
- **Example format:** total=average*count equation then unknown solve.
- **Verifier checks:** equations/computation present, numeric final.
- **Reject when:** missing equation or non-numeric final.

## Discovery vs selection failure connection
- Discovery failures: free-form candidates lacked stable structure, so quality could not be reliably measured.
- Selection failures: commit policy could not safely compare malformed candidates; schema grounding provides comparable, validator-passing candidates.

## Opt-in + dry-run rationale
- Keeps production path unchanged while validating parseability and structural success offline.
- Limits risk by requiring deterministic validation before any live integration.
