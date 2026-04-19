#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.diversity_needed_feasibility import DiversityNeededFeasibilityConfig, run_feasibility_pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bounded diversity-needed predictor feasibility pass")
    p.add_argument("--config", default="configs/diversity_needed_feasibility_v1.json")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cfg = DiversityNeededFeasibilityConfig(**payload)
    metrics = run_feasibility_pass(cfg)
    print(json.dumps({"run_id": cfg.run_id, "counts": metrics.get("counts", {}), "policy_gate_check": metrics.get("policy_gate_check", {})}, indent=2))


if __name__ == "__main__":
    main()
