# Stop-vs-act label-construction diagnosis note

## 1) Most likely label bottleneck
- Current uncertainty labeling treats any high rollout instability as uncertain, regardless of whether delta_mean is far from decision boundary.
- This likely over-marks uncertain examples and weakens label usefulness for training.

## 2) Evidence
- Mean uncertain rate (old rule): `0.8146`.
- Mean unstable rate: `0.8127`.
- Mean share of unstable examples with |delta_mean| > 0.150: `0.5026`.
- Mean uncertain rate among ACT labels: `0.9867`.
- Mean ACT label rate: `0.0243`.

## 3) One refinement to try
- Add an instability guard band (`instability_guard_band=0.150`): instability marks uncertainty only when `|delta_mean| <= guard_band`.
- Keep all other label/model components fixed.
