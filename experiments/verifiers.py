"""Pluggable verifier interfaces for verifier-guided test-time search (PRM-style extension point).

This module intentionally keeps scoring separate from candidate generation so a
process-level PRM (PRM800K-style) or a stronger ORM can replace the default proxy.
"""

from __future__ import annotations

from typing import Protocol

from experiments.branching import BranchState


class CandidateVerifier(Protocol):
    """Score a candidate branch after generation; higher is better."""

    def score(self, branch: BranchState, question: str) -> float:
        ...


class LLMVerifyProxyVerifier:
    """Uses the existing API `verify` path as a lightweight outcome-style verifier.

    This is a **proxy** (not a trained PRM): it consumes one verify call per candidate
    and maps the post-verify branch score into a scalar ranking signal.
    """

    def __init__(self, generator: "APIBranchGenerator") -> None:
        self._gen = generator

    def score(self, branch: BranchState, question: str) -> float:
        self._gen.verify(branch, question)
        return float(branch.score)


class SimulatedScorerVerifier:
    """Simulator-only verifier: ranks by branch score with small noise."""

    def __init__(self, rng: object) -> None:
        self._rng = rng

    def score(self, branch: BranchState, question: str) -> float:  # noqa: ARG002
        return float(branch.score) + 0.001 * float(self._rng.random())
