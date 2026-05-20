# RelationReady corruption pool QA v0

Purpose
- Convert clean candidate rows into deterministic synthetic negatives for RelationReady training.
- Keep the corruption pool local-only and deterministic so it can be regenerated from the same seed rows.

Why QA is required
- Synthetic corruptions can be trivial, malformed, or accidentally identical to the parent row.
- QA filters these rows before annotation or training, so the classifier learns hard semantic negatives instead of noisy artifacts.

QA checks
- Required labels/fields exist.
- Corrupted formula changes relative to the parent when a formula exists.
- Corrupted formula still parses.
- No gold fields appear in the model-input surface.
- Prompt/gold inconsistent seeds are marked `not_for_training` or excluded upstream.

Allowed into training
- Rows that pass QA and are not prompt/gold inconsistent.
- Rows must remain synthetic negatives with `relation_ready_label = not_ready`.

Not allowed
- Any held-out live/pilot slices used as seeds.
- Any prompt/gold inconsistent row.
- Any row with unchanged or broken formula.
- Any row exposing gold values in model-input fields.

Limitations of v0
- Heuristic corruption operators only.
- No semantic execution or model-based verification.
- Intended as a scaffold for later annotation, not a final dataset.
