# Stop-vs-act mixed-performance diagnosis note

## 1) Most likely bottleneck
- The dominant bottleneck is **uncertainty handling interacting with rare ACT labels**.
- Most examples are marked uncertain (mostly due to high delta instability), and ACT labels are very sparse.
- This makes generic uncertainty suppression (especially filtering) prone to removing/downweighting too much useful ACT signal.

## 2) Evidence
- Prior sweep learned-vs-heuristic was mixed: `{'wins': 13, 'losses': 11, 'ties': 0, 'total': 24}`.
- Mean label positive rate across bounded diagnosis grid: `0.0243`.
- Mean uncertain rate: `0.8146`.
- Mean unstable-rate component: `0.8127`.
- Mean uncertain rate among ACT-positive labels: `0.9867`.
- Mean uncertain rate among STOP labels: `0.8103`.
- Mean heuristic-label agreement: `0.7729` (suggesting limited room unless label signal is preserved better).

## 3) Single best lightweight revision to try next
- Add one training policy: **`downweight_nonpositive`**.
- Rule: only downweight uncertain examples when label is STOP(0); retain full weight for ACT(1) even if uncertain.
- Goal: reduce instability from uncertain negatives without suppressing scarce ACT supervision.
