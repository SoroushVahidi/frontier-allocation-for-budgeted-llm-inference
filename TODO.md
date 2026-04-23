# TODO (current maintenance backlog)

This backlog intentionally reflects the current NeurIPS-facing consolidation phase.

## Must keep current

- [ ] Keep front-door docs synchronized: `README.md`, `QUICKSTART.md`, `docs/CANONICAL_START_HERE.md`, `docs/REPO_MAP.md`, `docs/CANONICAL_INSTALL_AND_DEV.md`, `scripts/CANONICAL_START_HERE.md`.
- [ ] Keep manuscript claim boundaries synchronized with canonical artifact families (`docs/PAPER_SOURCE_OF_TRUTH.md`, `outputs/README.md`).
- [ ] Keep the `strict_f3` (manuscript matched surface) vs `strict_gate1_cap_k6` (broader operational surface) distinction explicit everywhere.

## Engineering hygiene

- [ ] Maintain lightweight checks (`make smoke`, `make health`, `make test`, `make check`) as low-friction defaults.
- [ ] Extend unit tests only for stable utility logic (avoid brittle tests around volatile exploratory scripts).
- [ ] Keep dependency files (`requirements*.txt`, `pyproject.toml`) consistent and minimal.

## Documentation debt (low-risk)

- [ ] Mark superseded notes as such rather than deleting provenance-important files.
- [ ] Reduce duplicate navigation language when updating canonical docs.
- [ ] Keep `docs/PAPER_BASELINE_HONESTY_STATUS.md` and `docs/PAPER_OPEN_GAPS_AND_RISKS.md` aligned with latest fairness-boundary docs.

## Explicitly out of scope for this TODO

- Rewriting historical experimental claims.
- Promoting supportive artifacts to canonical headline evidence without a canonical decision-doc update.
- Changing scientific conclusions without new artifact-backed evidence.
