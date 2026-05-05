# Current approaches status — 2026-05-05

This note organizes the recent research state for budgeted GSM8K-style inference. It separates **tested evidence**, **promising active directions**, **parked / abandoned directions**, and **API-backed artifacts to preserve**.

The goal is to prevent future agents from re-running old mistakes, over-claiming from small slices, or spending Cohere calls before the next diagnostic question is clear.

## Current north star

Primary external comparator:

```text
external_l1_max
```

Current best internal live line from recent work:

```text
direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak
```

Recent same-case 10-case diagnostic:

```text
outputs/cohere_external_l1_cached_vs_k1_frontier4_frontier_tiebreak_10case_20260505T004535Z/
```

Headline on that slice:

| Method | Exact |
|---|---:|
| cached `external_l1_max` | 8/10 = 80% |
| live `k1_frontier4_frontier_tiebreak` | 6/10 = 60% |
| gap | 20 percentage points |

Do not claim this closes the external gap. Do treat it as evidence that the project is no longer in the earlier broken-plumbing state.

## Bottleneck timeline

| Stage | Dominant bottleneck | Evidence / result | Status |
|---|---|---|---|
| Old strict-method comparisons | Old method was far behind `external_l1_max` | strict-F3 / strict-gate runs showed large gaps | Historical reference only |
| First diverse-root live comparison | Method adapter / answer surfacing broken | guarded method produced mostly null `predicted_answer` and very low exact | Fixed enough to move on |
| K3 root cap | Direct reserve consumed budget before frontier | k3 finished slices but frontier still did not run | Parked |
| K2 frontier reserve | Frontier ran but answers were not surfaced | frontier rows existed but final nodes / selected group path missed them | Fixed |
| K1 frontier-heavy | More frontier surface area | k1 improved coverage on selected k2-gold-absent cases | Active line |
| Frontier tiebreak | Gold was present but wrong group selected | offline 3/10 → 7/10; live same-case 6/10 | Best current line |
| Finalguard | Attempted to prevent weak/interim commits | offline replay 6/10 → 6/10, no fixes | Parked |
| Numeric leaf forcing | Attempted to force parseable numeric leaves | 118/800 smoke unchanged: 200 and 1 | Parked for now |

## Method status table

| Method / direction | Role now | Evidence | Decision |
|---|---|---|---|
| `external_l1_max` | Primary external baseline | Cached 10-case exact 8/10; earlier 30-case exact about 25/30 | Keep as baseline to beat |
| `strict_f3` | Old manuscript/reference anchor | Not current best; using it caused misleading comparison | Do not use as current target |
| `strict_gate1_cap_k6` | Old operational strict baseline | Older diagnostics only | Reference only |
| `direct_reserve_diverse_root_frontier_v1_guarded` | Merged guarded diverse-root base | Initially live-runnable after registry fix, but surfaced poorly before repairs | Superseded by k1/frontier variants for active debugging |
| `..._guarded_k3` | Reduce roots from 5 to 3 | Completed under cap, but frontier still did not run | Parked |
| `..._guarded_k2_frontier2` | Reserve budget for frontier | Frontier ran; later surfacing fixed; 10-case exact 2/10, gold-in-tree 4/10 | Superseded by k1 |
| `..._guarded_k1_frontier4` | Shift budget toward frontier | 5-case targeted run: exact 1/5, gold-in-tree 2/5; same-case k1 before tiebreak 3/10 | Foundation for best active line |
| `..._guarded_k1_frontier4_frontier_tiebreak` | Current best active line | Same-case live 6/10 vs external 8/10; no parse failures; present-not-selected 0/10 | Continue, but focus on remaining gold-absent / wrong-reasoning cases |
| `..._finalguard` | Guard against weak/interim fallback final answers | Offline replay no gain: 6/10 → 6/10 | Park; do not spend API now |
| `..._numeric_leaf` | Force numeric leaf fields in JSON | 118/800 smoke populated fields but exact unchanged 0/2 | Park; not worth broad rerun now |
| Cached verifier selector replay | Recovery-track selector evidence | Useful on candidate pools; not runtime-promoted | Keep as analysis tool, not headline |

## Current best interpretation

The live method is no longer primarily failing because of parser/surfacing bugs. The strongest current evidence says:

1. **Selection/commit was a major bottleneck** and the frontier tiebreak fixed much of it on the 10-case slice.
2. **The remaining gap is now mixed coverage and reasoning-path quality**, especially the cases where gold is absent from the explored tree or the method builds strong support for a wrong intermediate answer.
3. The next useful changes should target **better candidate generation / stronger direct reasoning seed**, not another small guard unless a specific offline replay shows net fixes.

## Case-level lessons from the latest gap

Important failure audit:

```text
outputs/failure_audit_l1_vs_k1_frontier_tiebreak_10case_20260505T004535Z/
```

Key external-correct / k1-wrong cases:

| Case | Gold / external | K1 answer | Lesson |
|---|---:|---:|---|
| `openai_gsm8k_118` | 1300 | 200 | Wrong supported consensus / likely interim or incomplete reasoning path |
| `openai_gsm8k_800` | 315 | 1 | No useful candidate/completion signal; repair-like fallback remained bad |

Both suggest that the next active line should improve **reasoning path quality** or add a stronger direct seed, not merely re-rank the existing candidates.

## Approaches to leave behind for now

Do not spend more API on these unless a new no-API replay gives a specific reason:

- broad reruns of `strict_f3` vs `external_l1_max`;
- k3-only variants;
- k2-frontier2 as a final method;
- finalguard as a live method;
- numeric-leaf broad reruns;
- selector-only experiments when gold-in-tree is low or the wrong answer has strong support.

## Approaches worth hope / active next lines

Most promising active families:

1. **Stronger direct seed + frontier hybrid**: add one more L1-like direct reasoning candidate as an incumbent / candidate source, then let frontier tiebreak override only with support.
2. **Coverage-aware frontier search**: use fewer shallow roots and more budget for branches that show equation progress.
3. **Cheap self-evaluation / progress pruning**: not a full verifier; just a low-cost branch-progress score to avoid spending frontier actions on stalled branches.
4. **Loss-case dataset**: expand from 10 cases to a curated set where `external_l1_max` is correct and k1 is wrong, then classify why before new structural changes.

## API discipline

Use API when it answers a named diagnostic question. Avoid API when the answer can be obtained from existing JSONL/CSV artifacts.

Good API question examples:

- Does a new live method actually populate required metadata fields?
- Does a no-API replayed selector gain transfer to fresh live traces?
- On the same case IDs, how far is current best from cached `external_l1_max`?

Bad API question examples:

- Broad rerun before fixing a known surfacing bug.
- Rerun of a method whose offline replay showed 0 net gain.
- External comparison using an old or unintended method ID.

## Claim boundary

Safe current claim:

```text
On a small same-case 10-case Cohere diagnostic, frontier tiebreak improved the internal method from 3/10 to 6/10 and reduced the gap to cached external_l1_max from 50 percentage points to 20 percentage points. This is promising but not a broad win.
```

Unsafe current claim:

```text
The method defeats external_l1_max.
```
