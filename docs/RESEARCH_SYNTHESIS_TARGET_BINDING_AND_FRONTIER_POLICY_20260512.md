# Research Synthesis: Target Binding Failure and Frontier Edge Policy
**Date:** 2026-05-12  
**Repository:** frontier-allocation-for-budgeted-llm-inference  
**Status:** Active research direction — do not claim accuracy improvements until held-out live evidence

---

## 1. Empirical Failure Pattern

### The core failure: final-target binding

The dominant observed failure mode across the wrong-supported-consensus slice is **final-target binding failure**: the frontier generates candidates that are locally coherent (syntactically correct, numerically plausible, target-aligned by proxy score) but answer a different question than asked.

Recurring sub-patterns:

| Sub-pattern | Example |
|---|---|
| Profit vs sale price | Computes total revenue, not profit after costs |
| Difference vs total | Returns `a + b` when question asks `a − b` |
| Original-before-process vs after | Returns "after" state when "before" is the target |
| Per-unit/share vs total | Returns `total / n` when `n × unit_cost` is needed |
| Unit conversion | Returns source units, not converted units |
| Ratio/percentage base | Returns numerator or product, not the ratio/percentage |

These are **answer-structure** errors, not arithmetic errors. The model sets up the problem correctly but binds the final answer to the wrong intermediate value.

### Evidence from 97 wrong-supported-consensus cases

- **70/97** (72%) cases: gold answer absent from the candidate pool entirely — the controller never generated a candidate with the correct final target
- **21/97** (22%) cases: gold present in pool but not selected by the ensemble
- **6/97** (6%) unclear / other

The 70 gold-absent cases are the structurally hard ones. Even perfect reranking cannot recover them; the correct answer was never generated.

### Prompt-only final-transform branch pilots (Cohere command-r-plus-08-2024)

Four successive 12-case pilots on the gold-absent slice:

| Version | Exact | Key issue |
|---|---|---|
| v1 | 0/12 | Salient-intermediate anchoring; base prompt too weak |
| v2 | 1/12 | Anti-anchoring added; one case solved |
| v3 | 2/12 | Parser bug ($-prefix): case 1029 silently wrong |
| v4 | 2/12 | Parser fixed; regression on case 1021 from prompt wording change at temp=0 |

**Conclusion:** Prompt micro-tuning produces noisy, unstable, marginal gains. The gate condition (exact ≥ 3/12 to justify a 30-case pilot) was not met across four rounds. The structural issue is not addressable by prompt adjustment alone.

---

## 2. Reason for Failure

**Why does the frontier produce wrong-target candidates so reliably?**

1. **Locally coherent but globally mistargeted reasoning.** Chain-of-thought models tend to produce a final arithmetic step that is internally consistent with their own intermediate steps, even when those intermediates are the wrong target for the question.

2. **No explicit target variable binding.** The model generates a narrative answer rather than resolving a named target variable. Without an explicit `target_variable = <name>`, the model's "final answer" may bind to the last or largest value rather than the question's asked quantity.

3. **Correct candidate structurally absent.** For 70/97 cases, the candidate pool contains only wrong-target answers. The verifier/backward-from-target-check branch (`backward_from_target_check`) was not allocated to these cases by the controller — its absence means the pool contains no backward-validated candidate, and all reranking operates over a pool with no correct answer.

4. **Ensemble amplifies the wrong target.** When 3–4 of 5 branches produce the same wrong-target answer, the majority vote / support-count selector confidently selects it. High support = high confidence in the wrong answer.

5. **Prompt tuning cannot fix structural gaps.** A prompt that says "find the profit" can still generate a revenue answer if the model's chain-of-thought doesn't isolate the correct target operand. The fix requires a structural representation layer, not a prompt instruction.

---

## 3. Literature / Research Synthesis

### GSM8K Verifiers (Cobbe et al., 2021)
**Finding:** Training a separate verifier on reasoning steps — outcome reward model (ORM) or process reward model (PRM) — substantially improves accuracy on grade-school math over greedy decoding.  
**Project implication:** The `backward_from_target_check` branch is an inference-time analog of a verifier: it attempts to validate whether a candidate answer actually satisfies the question's target conditions. The high lift of the `PAL_code → verifier_check` transition (1.60, support 22, precision 0.95) suggests that a runtime process verifier is the strongest available signal. The key gap: 70 cases never ran the verifier at all.

### PAL (Gao et al., 2022)
**Finding:** Program-Aided Language Models that emit executable code and run it via a Python interpreter achieve large accuracy gains over chain-of-thought alone, especially for multi-step arithmetic.  
**Project implication:** PAL execution is already in the frontier (`pal_code_with_required_target_variable`). The current limitation is that PAL code emits a numeric result without naming which variable it corresponds to. A `target_variable_dict` extension — where the PAL code explicitly assigns `target = ...` and returns a dict — would directly address the binding failure by forcing the code to identify its target.

### Semantic Parsing for Word Problems (Kushman et al., 2014; Roy & Roth, 2015, 2018)
**Finding:** Decomposing word problems into equation templates with named unknowns, then solving symbolically, achieves strong accuracy on arithmetic word problems.  
**Project implication:** The `declarative_equation_branch` direction (see §5) is directly inspired by this: generate an explicit equation system with a named target variable (`target = ...`) and solve it. This addresses binding failure at the representation level — the solver must commit to a target before computing a value.

### LLM + Symbolic Solver / Declarative Equation Solving
**Finding:** Hybrid systems that use LLMs to formalize problems into declarative representations (equations, z3 constraints, Lean/Prolog) and then call a solver achieve better reliability than pure LLM generation, especially on problems requiring precise quantity binding.  
**Project implication:** Directly supports `declarative_equation_branch_v1`. Even a lightweight approach — emit `target_variable`, emit equations as Python expressions, solve with `sympy` or `exec` — would help. Does not require training.

### Tree of Thoughts / ReAct (Yao et al., 2023, 2022)
**Finding:** Structuring generation as a search tree with explicit branching, evaluation, and backtracking dramatically improves performance on problems requiring multi-step planning. ReAct interleaves reasoning and action steps with observation loops.  
**Project implication:** The colored-edge sequence framework already approximates a reasoning tree: each branch family is a node, the sequence of branch colors is a path, and transition-rule lifts approximate path values. The missing piece is a learned next-edge policy that decides which unexplored edge is worth generating. This directly motivates `frontier_next_edge_policy_v1`.

### Process Reward Models (Lightman et al., 2023)
**Finding:** PRMs trained to score individual reasoning steps outperform ORMs on mathematical reasoning, enabling efficient best-first search over reasoning paths.  
**Project implication:** The `backward_from_target_check` branch is a hand-designed process verifier. A PRM trained on (path, step, quality_label) triples from existing traces could replace or augment it. For now, the offline lift-based scoring (transition rules from `mine_reasoning_edge_sequences.py`) approximates a PRM signal without training.

### Adaptive Compute / Uncertainty-Aware Tree Search
**Finding:** Recent work allocates compute dynamically based on per-instance difficulty or uncertainty, achieving better accuracy-per-FLOPs tradeoffs than uniform search.  
**Project implication:** The budget-allocation framing of this project is directly aligned. The feature contrasts from `mine_frontier_node_distribution.py` show that `numeric_range`, `numeric_ratio_spread`, and `candidate_values_cluster_count` correlate with proxy improvement — these are uncertainty signals. A simple rule (`if numeric_range > threshold → allocate extra verifier branch`) would be a tractable adaptive compute heuristic.

### Contextual Bandits / Graph Search / Learning to Search (Chang et al., 2015; He et al., 2012)
**Finding:** Treating sequential decision problems (e.g., parsing, structured prediction) as a contextual bandit or imitation-learning-from-search problem allows learning good exploration policies from expert demonstrations.  
**Project implication:** The colored-edge framework is a natural fit: state = current set of candidate edge colors, action = which next edge to generate, reward = proxy quality improvement. The offline lift scores are a first-pass policy; a learned policy from held-out traces would be `frontier_next_edge_policy_v1`.

---

## 4. Reliability Ranking

**Strong / foundational — high confidence in project applicability:**
- GSM8K verifiers (ORM/PRM): target-validation is the clearest offline signal
- PAL: code execution is already integrated; target-variable-dict is a natural extension
- Semantic parsing / declarative equation solving: directly addresses binding failure
- Tree of Thoughts / ReAct: search tree framing matches the colored-edge framework

**Strong but specialized — worth pursuing after foundational work:**
- Symbolic solver integration (sympy/z3): high value but requires equation formalization
- Process reward models: high accuracy ceiling but require training data

**Promising but cautious — use insights, not direct methods:**
- Adaptive compute / uncertainty-aware tree search: inspiring but complex to implement correctly; start with hand-crafted heuristics
- Contextual bandits: strong theoretical grounding, but small dataset (97 cases) limits reliable policy learning

---

## 5. Recommended Algorithmic Directions

### High priority

**`frontier_next_edge_policy_v1`**  
Learn (or derive via held-out cross-validation) a next-edge allocation policy using colored-edge sequence features + node-distribution features as state, and proxy improvement / exact accuracy as reward.  
- Use existing `transition_rules.csv` and `frontier_feature_rows.csv` as feature sources
- Held-out split: train on 70 cases, test on 27 (or leave-one-out)
- Policy output: which branch family to allocate next given current candidate set
- No API needed for initial offline experiment

**`target_variable_dict_pal_branch_v1`**  
Modify/add a PAL branch that emits a named-variable dict:
```python
result = {
  "target_variable": "profit",
  "target_value": revenue - cost,
  "intermediate": {"revenue": ..., "cost": ...}
}
```
The PAL executor can then extract `target_value` rather than the last numeric expression, directly addressing the final-target binding failure.
- No training required
- Implementable as a new branch prompt + extraction rule
- Can be preflight-tested offline before live API pilot

**`declarative_equation_branch_v1`**  
Generate an equation system with explicit target variable, then solve:
```python
# Generated by LLM:
equations = ["revenue = 3 * price", "cost = 2 * price", "profit = revenue - cost"]
target = "profit"
# Solved by runtime:
import sympy; ...
```
- Addresses binding failure at representation level
- Deterministic solver means no hallucinated arithmetic
- Can be validated offline on known cases

### Medium priority

**Target-sensitive verifier / process verifier**  
Extend `backward_from_target_check` to explicitly reason about "does this answer bind to the correct target variable?" rather than just "is this answer target-aligned by proxy score?"

**Verifier-guided generation**  
Rather than generating N candidates then verifying, use the verifier signal mid-generation to steer toward target-aligned completions.

**Uncertainty-aware budget allocation**  
Use `numeric_range`, `numeric_ratio_spread`, and `candidate_values_cluster_count` as difficulty signals to allocate additional branches only when uncertainty is high.

### Low priority (defer)

- RL/fine-tuning on this dataset: too small (97 cases), noisy labels
- Dataset augmentation: not a priority until structural fixes show signal
- More prompt micro-tuning: v4 pilot confirmed diminishing returns

---

## 6. Recommended Next No-API Experiments

**Step A: Held-out next-edge prediction**  
Split 97 cases into train/test. Train a simple logistic regression or rule-based classifier on `(colored_edge_sequence_features, node_distribution_features) → should_allocate_verifier_check`. Evaluate on held-out split.  
Target file: `scripts/train_next_edge_policy_v1.py`

**Step B: Target-variable-dict PAL preflight scaffold**  
Write a prompt template for the new PAL branch that emits a named-variable dict. Test offline against known wrong-consensus cases to check if the generated code correctly isolates the target variable.  
Target file: `prompts/target_variable_dict_pal_v1/branch.md`

**Step C: Declarative equation branch preflight**  
Write a prompt that asks the model to emit equations + target variable, then validate that a local solver (sympy) can extract the correct answer on a small set.  
Target file: `scripts/preflight_declarative_equation_branch.py`

**Step D: Joint policy**  
Combine the next-edge policy (Step A) with the colored-edge lift scores as a unified scoring function. Use both to decide: (a) which existing candidate to select, and (b) which missing branch to allocate in a live experiment.

---

## 7. Safe Claims / Unsafe Claims

### Safe to claim
- This project has identified **final-target binding failure** as the dominant manually observed mechanism in the wrong-supported-consensus slice of GSM8K.
- **Prompt-only branches show weak but non-zero signal**: v2 1/12, v3–v4 2/12 exact across four pilots. Signal is real but too small for production use.
- **The stronger direction is structural target representation + budgeted edge allocation**: the offline evidence (verifier lift=1.60, verifier alignment=97%, ML AUC=0.78 for proxy prediction using node-distribution features) supports this direction.
- **Offline replay is insufficient for the 70 gold-absent cases**: correct answers are structurally absent; no reranking can recover them.

### Unsafe to claim (do not assert until live evidence exists)
- Any accuracy improvement over external_l1_max or any published baseline — no live experiment has been run that meets a held-out evaluation standard
- That the colored-edge policy improves accuracy at inference time — offline proxy metrics were negative (net −33) on the available 47-case subset; this does NOT mean the policy is wrong, only that it needs live allocation to test
- That prompt tuning solves the problem — four pilots definitively show it does not
- That the frontier node-distribution features generalize beyond this 97-case slice — no held-out evaluation has been run

---

## 8. Current Roadmap

| Step | Description | Status |
|---|---|---|
| 1 | Preserve research synthesis memo (this document) | **Done** |
| 2 | Commit diagnostic tools: `mine_reasoning_edge_sequences.py`, `replay_colored_reasoning_path_policy_v1.py`, `mine_frontier_node_distribution.py` (with tests) | Pending explicit commit request |
| 3 | Implement held-out next-edge prediction (`frontier_next_edge_policy_v1`) | Not started |
| 4 | Implement target-variable-dict PAL scaffold (`target_variable_dict_pal_branch_v1`) | Not started |
| 5 | Run Cohere-only fixed-budget live pilot **only after** no-API held-out evidence is strong (e.g., AUC > 0.80 on held-out split for next-edge prediction) | Blocked on Steps 3–4 |

---

## Appendix: Key Files and Outputs

| File / Output | Purpose |
|---|---|
| `scripts/mine_reasoning_edge_sequences.py` | Builds colored edge paths, mines motifs and transition rules from traces |
| `scripts/replay_colored_reasoning_path_policy_v1.py` | Applies transition-rule lifts to rerank existing candidates |
| `scripts/mine_frontier_node_distribution.py` | Extracts node-distribution features; heuristic missing-edge recommendations |
| `/tmp/reasoning_edge_sequence_mining_v1_wrong_consensus_97/` | Mined paths, 49 motifs, 43 transitions, lift index |
| `/tmp/colored_reasoning_path_policy_v1_replay_wrong_consensus_97/` | Policy replay: 7 proxy fixes, 40 regressions, 61 cases need live VC |
| `/tmp/frontier_node_distribution_mining_v1_wrong_consensus_97/` | 55 features/case, ML AUC 0.78 for proxy, 61 VC recommendations |
| `prompts/final_transform_branch_generation_v1/` | 7 branch prompts, 4-pilot history, currently gated at ≥ 3/12 exact |
