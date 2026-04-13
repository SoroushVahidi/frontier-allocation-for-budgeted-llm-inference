#!/usr/bin/env python3
"""Cheap smoke test for verifier_guided_search and program_of_thought (simulator only)."""

from __future__ import annotations

import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import ProgramOfThoughtController, VerifierGuidedSearchController
from experiments.scoring import ScoreConfig, SimpleBranchScorer
from experiments.verifiers import SimulatedScorerVerifier


def main() -> None:
    rng = random.Random(0)
    gen = SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
    scorer = SimpleBranchScorer(ScoreConfig())
    budget = 12
    vgs = VerifierGuidedSearchController(
        gen,
        scorer,
        budget,
        n_candidates=3,
        verifier=SimulatedScorerVerifier(rng),
        min_expansions_per_candidate=1,
    )
    pot = ProgramOfThoughtController(gen, scorer, budget)
    q = "Alice has 12 apples and buys 5 more. How many apples?"
    gold = "17"
    r1 = vgs.run(q, gold)
    r2 = pot.run(q, gold)
    assert r1.metadata.get("verifier_scores") is not None
    assert "pot_output" in r2.metadata
    print("verifier_guided_search ok:", r1.is_correct, "actions", r1.actions_used)
    print("program_of_thought ok:", r2.is_correct, "actions", r2.actions_used)


if __name__ == "__main__":
    main()
