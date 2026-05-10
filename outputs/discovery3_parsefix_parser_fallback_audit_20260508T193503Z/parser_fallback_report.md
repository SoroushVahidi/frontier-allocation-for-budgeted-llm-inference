# parser fallback report

- Scope: no-API audit/rescore of existing 5-case parsefix live responses.
- Conservative precedence used: strict `FINAL_ANSWER` -> alias final-answer line -> boxed numeric -> last numeric-only line.
- Gold was used only for post-hoc exact computation, never for candidate selection.
- Alias patterns found: none.
- Parsing failures: 3 -> 3.
- Exact count: 0 -> 0 (gain 0).
- Ambiguous cases: 0.
- Parser patched in codebase: True.
- Ready for another 5-case live recheck: True.
- Ready for 15-case rerun: False.
