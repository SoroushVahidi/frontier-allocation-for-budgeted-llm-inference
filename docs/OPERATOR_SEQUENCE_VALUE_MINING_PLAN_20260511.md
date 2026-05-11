# Operator Sequence Value Mining Plan

## Goal

Mine completed reasoning traces as operator-labeled paths so we can estimate which operator sequences, path prefixes, and local subtree features predict endpoint quality.

This is an offline mining scaffold, not a live controller. The immediate target is to learn predictive signal from completed traces first, then use that signal in later controller work only after separate validation.

## What This Is Not

- Not a PRM-only verifier project.
- Not a Tree-of-Thoughts reimplementation.
- Not a runtime policy change.
- Not a claim of superiority over any external baseline.

## Core Idea

Each reasoning trace can be viewed as a path in a tree or graph. Every node or edge can carry an operator label such as:

- `direct_l1_anchor`
- `equation_first_anchor`
- `unit_ledger_money_anchor`
- `ratio_percentage_anchor`
- `backward_check_anchor`
- `PAL` or code reasoning
- repair or extraction
- uncertainty retry
- frontier continuation

The question is whether operator sequences and local graph features predict whether a partial path is likely to end well.

Examples of useful hypotheses:

- If `A -> B -> A` often ends correct, then a future controller seeing `A -> B` may want to try `A` next.
- If the best descendant quality is improving while sibling agreement is increasing, the controller may want to continue.
- If entropy is high, support is split, and the current answer is an outlier, the controller may want to abandon or branch differently.

## Intended Outputs

The mining scaffold should support four offline row types:

- Node rows
- Edge rows
- Path-prefix rows
- Subtree rows

The first PR only needs the path-prefix feature scaffold, but the output schema should be compatible with the others.

## Label vs Feature Separation

Offline labels may use gold. Runtime-style features must not.

Labels that may use gold:

- terminal correctness
- gold in subtree
- best-descendant correctness
- endpoint quality
- delta quality after an operator choice

Runtime-style features that must stay gold-free:

- operator sequence n-grams
- support counts
- entropy
- support margin
- outlier flags
- subtree shape
- sibling agreement
- cross-operator convergence
- best-descendant quality estimated from observed trace quality only

The critical rule is that labels can look at gold, but features used for later runtime models must be computed without gold leakage.

## First Models

Start with simple, transparent models:

- n-gram tables over operator sequences
- logistic regression
- small tree models

Do not start with a GNN.

## Evaluation

Evaluate offline with:

- AUROC and calibration for best-descendant correctness
- oracle next-operator agreement
- regret to the oracle action
- replay-level gold-in-pool and collapse diagnostics

The evaluation should stay offline and replay-scoped. Any later controller use requires a separate validation stage.

## Guardrails

- No API calls
- No runtime default change
- No external-baseline claim
- No gold leakage into runtime features
- Keep provenance explicit for any artifact-based labels

