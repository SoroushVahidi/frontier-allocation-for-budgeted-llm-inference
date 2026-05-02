# Blocker: paired-case batch execution attempt in interactive runtime

Attempted paired-case batch mode with real Cohere and explicit cap (`max_calls=3100`) for target 25 paired cases.
The run started and created per-case allow-list checkpoints, but no complete paired triple finished before interactive runtime interruption.

This confirms the implementation now attempts per-case batching, but longer uninterrupted runtime is still required to accumulate complete paired rows.
