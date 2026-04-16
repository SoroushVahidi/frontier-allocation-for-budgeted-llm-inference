# Direct comparator note for arXiv:2602.01070

This note records the current recommended handling of the paper:

- *What If We Allocate Test-Time Compute Adaptively?* (arXiv:2602.01070)

## Current repo interpretation

This paper is important because it appears to be one of the strongest **direct conceptual comparators** for the current project's frontier-allocation direction.

However, the repository should **not** currently treat it as:
- an official-code baseline,
- an import-validated package baseline,
- or an official reproduction target.

The best current interpretation is:

> **paper-faithful reimplementation candidate from public paper specification**

## Why this conservative handling is necessary

Recent review of accessible materials indicated:
- no author-released code repository was clearly verified for this paper,
- no import-ready official evaluation package was established,
- and no clean official-results artifact path was identified.

At the same time, the paper appears to provide enough detail to motivate a careful reimplementation track.

So this comparator belongs in the repo as:
- a paper-positioning reference now,
- and a future reimplementation candidate if the implementation contract is written down carefully.

## Safe wording

Safe:
- paper-faithful reimplementation candidate,
- reimplemented from public paper description,
- direct conceptual comparator,
- no official code confirmed at time of repo update.

Unsafe:
- official reproduction,
- author implementation baseline,
- import-validated official package,
- official results replication.

## Practical implication

If this paper is implemented in the repo later, the implementation note should explicitly separate:
1. details directly specified in the paper,
2. details that required engineering choices,
3. and any deviations from the paper description.

That keeps the comparison reviewer-defensible even without an official code release.
