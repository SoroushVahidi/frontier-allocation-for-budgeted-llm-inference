# Cascade routing — unified routing and cascading (Dekoninck et al., ICML 2025)

- **Canonical title:** *A Unified Approach to Routing and Cascading for LLMs*
- **Paper (PMLR / proceedings):** https://proceedings.mlr.press/v267/dekoninck25a.html
- **OpenReview:** https://openreview.net/forum?id=rgDwRdMwoS
- **ICML 2025 poster:** https://icml.cc/virtual/2025/poster/46183
- **ETH SRI publication page:** https://www.sri.inf.ethz.ch/publications/dekoninck2024cascaderouting
- **Official code (ETH SRI org):** https://github.com/eth-sri/cascade-routing
- **License (GitHub API, verification time):** **Apache-2.0**
- **Import status:** **Linked only** — no submodule, no vendored code in this repo.
- **Role for this project:** Baseline for **routing and cascading across model tiers** under cost constraints; complements cross-controller frontier allocation (heterogeneous families, budget-aware selection).

## Setup notes (upstream)

```bash
git clone https://github.com/eth-sri/cascade-routing.git
```

## Integration scaffold (this repo)

- Registry entry: `configs/external_baselines_registry.json` → `cascade_routing`
- This directory contains **documentation only**.
