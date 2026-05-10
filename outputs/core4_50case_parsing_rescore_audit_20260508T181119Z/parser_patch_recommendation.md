# Parser patch recommendation

- Safely fixable now (method-agnostic conservative extraction): 0/29.
- Not safely fixable from saved artifacts: 29/29 (mostly no final answer emitted/forced continuation or ambiguous numbers).
- Recommendation: do not patch parser yet in this step; first add richer raw completion capture for all methods, then patch extraction with strict phrase-gated rules.
- Candidate safe parser changes (future): prioritize explicit final-answer phrases and boxed numbers before fallback numeric heuristics.
- Risk: broad last-number heuristics can overfit style and silently increase false positives; avoid method-specific hacks or gold-informed disambiguation.
