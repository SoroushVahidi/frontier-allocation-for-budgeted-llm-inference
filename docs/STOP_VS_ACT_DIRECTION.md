# Stop-vs-act method direction (canonical near-term)

## Decision question

At each allocation step, ask:

> **Is the next unit of compute worth spending here?**

This action-conditional question is the canonical controller framing for the next implementation phase.

## Why prefer binary stop-vs-act first

Compared with a first-pass continuous marginal-value regressor, binary stop-vs-act is currently preferred because:

1. Continuous value targets are more expressive but significantly noisier under proxy supervision.
2. Binary targets are usually more stable and less brittle with approximate labels.
3. The current project need is a reliable first decision rule, not a high-variance fine-grained estimator.
4. Uncertainty-aware stopping/routing has strong support in nearby literature.

## Role of pairwise BT branch scoring

Pairwise BT branch scoring remains central and useful:
- as a strong baseline,
- as an active branch of work,
- and as a potential component for richer later controllers.

But it is not, by itself, the clearest first controller for the next phase.

## First implementation sketch

- Model type: lightweight classifier.
- Input: branch/frontier state features + remaining budget + uncertainty indicators.
- Output: stop vs act probability (or score thresholded by budget policy).
- Training data: approximate marginal labels (stop-vs-one-more-action and short-horizon deltas).
- Training policy: uncertainty-aware filtering/reweighting.
- Evaluation: matched-budget controller-level comparisons versus strong heuristics and BT baseline.

## How to use uncertainty

Use uncertainty in two places:

1. **Inference-time feature**
   - include confidence/ambiguity proxies in controller input.

2. **Training-time data policy**
   - downweight or filter high-ambiguity examples,
   - optionally maintain a flagged ambiguous split for diagnostics.

## Later upgrades

After stable binary controller behavior:
- calibrated multi-threshold stop-vs-act policies,
- hybrid controller combining BT ranking with stop-vs-act gate,
- eventually continuous marginal-value modeling if labels and calibration improve.
