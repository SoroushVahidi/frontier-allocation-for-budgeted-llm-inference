# Main bottleneck focus (2026-04-18)

## Purpose

This note exists so the repository has one short file that answers:

> **What is the single most important bottleneck right now?**

## Short answer

The main bottleneck is:

> **supervision target quality / proxy-label mismatch for the next-step branch-allocation decision**

A sharper current phrasing is:

> **principled selective pairwise control and supervision design for ambiguous hard cases.**

## What that means in practice

The current method still struggles because the training targets are often too close to brittle local winner labels, while the deployed action is richer:
- which branch should receive the next unit of compute,
- under remaining budget,
- and when should the system explicitly avoid forced commitment?

## How the bottleneck appears

- noisy branch-comparison targets,
- low-margin ambiguity,
- near-tie instability,
- shallow comparator semantics,
- weak transfer of calibration across settings,
- and unresolved defer/fallback behavior on the hardest cases.

## What is *not* the main bottleneck now

The repo is not mainly blocked by:
- infrastructure completeness,
- another controller family,
- heavier models,
- or broader sweeps alone.

Those may still matter later, but they are not the highest-leverage next fix.

## Strongest current implication

The most promising next work should increasingly look like:
- better target semantics,
- more opportunity-cost-aware branch comparison,
- more faithful value-style or penalized-marginal targets,
- and clearer defer/unresolved treatment for hard ambiguous pairs.

## Current safe summary

A safe one-sentence summary is:

> The repository’s main unresolved issue is still target semantics for hard next-step branch-allocation decisions, especially where ambiguity is real and forced binary commitment is too brittle.
