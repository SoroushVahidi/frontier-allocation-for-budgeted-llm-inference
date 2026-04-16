# OpenR (OpenReasoner)

- **Repository:** https://github.com/openreasoner/openr
- **License (GitHub API, verification time):** **MIT**
- **Import status:** **Runnable-adjacent** via strict import validation (no submodule, no vendored code in this repo).
- **Role for this project:** Optional **open reasoning / process** stack for comparisons; useful as ecosystem reference when discussing verifier-guided or process-heavy pipelines (evaluate fit per experiment).

## Setup notes (upstream)

```bash
git clone https://github.com/openreasoner/openr.git
```

## Integration scaffold (this repo)

- Registry entry: `configs/external_baselines_registry.json` → `openr`
- Canonical integration note: `docs/openr_integration.md`
- Validator: `scripts/verify_openr_import.py`
- Status artifacts:
  - `outputs/external_baseline_completeness/openr_status.json`
  - `outputs/external_baseline_completeness/openr_status.md`
- This directory contains **documentation only**.
