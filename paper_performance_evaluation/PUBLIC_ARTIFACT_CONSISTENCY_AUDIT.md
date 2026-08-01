# Public Artifact Consistency Audit

Date: 2026-08-01

Scope: targeted pre-submission correction pass for the Performance Evaluation manuscript and public
artifact package. No new experiments, live API calls, scientific-result changes, or broad manuscript
rewrites were performed.

## Inconsistencies Found

1. The identified manuscript and declarations cited an obsolete fixed commit that did not contain
   the current 33-page manuscript and corrected artifact documentation.
2. The root and supplementary claim-evidence maps pointed to unavailable working directories:
   majority analysis, FIX-ablation, repair quantification, researcher-adaptation chronology, and a
   canonical-state file not present in the public checkout.
3. The claim-evidence map described compute accounting as archived outside the public release.
4. Several audit files reported stale page counts: 30/32 or 36/36 instead of the current 33/33 PDF
   builds.
5. The manuscript's reproducibility wording described released per-example record replay, while the
   public checkout exposes aggregate audit records, source tables, manifests, and scripts for
   aggregate-record verification of the reported aggregate results.

## Corrections Made

- Replaced the obsolete fixed-commit citation with the fixed public artifact commit used by the
  manuscript.
- Rebuilt `CLAIM_EVIDENCE_MAP.md` to cite only public tracked files, source tables, source sections,
  and the submission package.
- Added `CLAIM_EVIDENCE_PUBLIC_MAP.md` as an explicit public-facing map.
- Updated the supplementary claim map to the same public evidence boundary.
- Narrowed manuscript reproducibility wording from per-example replay to public aggregate-record
  verification.
- Updated data/code availability wording from "frozen processed records" to "frozen aggregate audit
  records."
- Updated stale page-count audits to 33 anonymous / 33 identified pages.
- Removed references to unavailable evidence routes from public-facing maps.

## Headline Claim Verification

Read-only verification against public CSVs and source tables confirmed:

- Completed cells: 15 completed cells and one Fireworks x GPQA-Diamond protocol-blocked cell.
- Completed-cell paired examples: n=3394.
- FTA aggregate: 2206/3394.
- Pooled-4 aggregate: 2258/3394.
- Frontier aggregate: 2176/3394.
- McNemar p-value from discordants 73/125: 0.00026908, reported as approximately 0.00027.
- Azure FIX-2 rescue/regression patterns: 2/18 for GSM8K and 7/31 for MATH-500.
- Fireworks x GPQA-Diamond status: `BLOCKED_PROTOCOL_NONCONVERGENCE`.
- Source tables retain the reported 2.78 to 5.38 call reconstruction, 276/300 same-model control,
  151/3394 repair asymmetry, and Pooled-4 15/15 held-out fold selection.

## Public Evidence Boundary

The public release supports deterministic checking of aggregate records and manuscript source
tables. It does not claim to regenerate closed-API completions, reconstruct every historical subset
draw, or expose the earlier working directories used during manuscript development.

## Validation Status

Completed before the first public artifact commit:

- Root anonymous manuscript compile: succeeded; 33 pages.
- Root identified manuscript compile: succeeded; 33 pages.
- Flat anonymous manuscript compile: succeeded; 33 pages.
- Flat identified manuscript compile: succeeded; 33 pages.
- Headline aggregate checks: passed.
- Public claim-map path check: passed.
- Source ZIP extraction: passed.
- Supplementary ZIP extraction: passed.
- Supplementary checksum validation: passed.
- Stale-reference scans for obsolete commit, unavailable working directories, unresolved placeholders,
  and repository-report phrases: passed.
- Anonymous PDF metadata: `Anonymous Author(s)`.
- Identified PDF metadata: `Soroush Vahidi`.

First public artifact commit: `dfc9997d803199d699e23ee42cfe0777e6d78155`.

Final public-release finalization commit after the artifact citation and package refresh:
`b5c8b1032205007ae5fd5fbc1fb4665e5aff0177`.

The final pushed `origin/main` state was validated after the artifact commit citation and package
refresh. The manuscript cites the fixed public artifact commit; the later public-release finalization
commit records the citation and packaging finalization.
