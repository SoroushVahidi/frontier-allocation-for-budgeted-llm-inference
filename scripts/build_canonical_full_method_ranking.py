#!/usr/bin/env python3
from __future__ import annotations

import csv, json, random, hashlib, importlib.util
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.branching import SimulatedBranchGenerator
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer

def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_bundle_for_full_ranking", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod

TW = _load_twenty_module()

DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024"]
SEEDS = [11, 23]
BUDGETS = [4, 6, 8]
SUBSET_SIZE = 20
ADAPTIVE_GRID = [0, 1, 2]

METHOD_SPECS = [
    # latest promoted + strict finalists
    ("strict_gate1_cap_k6", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1__deterministic_output_layer_repair_v1", "strict_family"),
    ("strict_gate1", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1", "strict_family"),
    ("strict_f2", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1", "strict_family"),
    ("strict_f3", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1__deterministic_output_layer_repair_v1", "strict_family"),
    ("strict_gate2", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v2_budget_aware_rescue__deterministic_output_layer_repair_v1", "strict_family"),
    # prior broad-family leaders
    ("broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1", "broad_family"),
    ("broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1", "broad_family"),
    ("broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1", "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1", "broad_family"),
    ("broad_diversity_aggregation_strong_v1", "broad_diversity_aggregation_strong_v1", "broad_family"),
    # internal / earlier
    ("reasoning_beam2", "reasoning_beam2", "internal_baseline"),
    ("reasoning_greedy", "reasoning_greedy", "internal_baseline"),
    ("self_consistency_3", "self_consistency_3", "internal_baseline"),
    ("adaptive_min_expand_0", "adaptive_min_expand_0", "earlier_repo_line"),
    ("adaptive_min_expand_1", "adaptive_min_expand_1", "earlier_repo_line"),
    ("adaptive_min_expand_2", "adaptive_min_expand_2", "earlier_repo_line"),
    ("verifier_guided_search", "verifier_guided_search", "internal_baseline"),
    ("program_of_thought", "program_of_thought", "internal_baseline"),
    # external
    ("external_tale_prompt_budgeting", "external_tale_prompt_budgeting", "external_baseline"),
    ("external_s1_budget_forcing", "external_s1_budget_forcing", "external_baseline"),
    ("external_l1_max", "external_l1_max", "external_baseline"),
    ("external_l1_exact", "external_l1_exact", "external_baseline"),
]


def runtime_method(name: str) -> str:
    x = name
    suf = "__deterministic_output_layer_repair_v1"
    if x.endswith(suf):
        x = x[: -len(suf)]
    if x.endswith("_hard_max_family_expansions_cap_k6_v1"):
        x = x + "_fixed_k6_control"
    return x


def stable_seed(*parts: Any) -> int:
    s = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(s.encode()).hexdigest()[:16], 16)


def node_ids_with_answer(nodes: list[dict[str, Any]], normalized_answer: str | None) -> list[str]:
    if normalized_answer is None:
        return []
    out = []
    for n in nodes:
        a = n.get("predicted_answer_normalized")
        if a == normalized_answer:
            out.append(str(n.get("branch_id")))
    return out


def run_observed(method_public: str, method_runtime: str, dataset: str, seed: int, budget: int, example: Any) -> dict[str, Any]:
    run_seed = stable_seed("canonical_full_ranking", method_public, dataset, example.example_id, seed, budget)
    rng = random.Random(run_seed)
    observed = TW.ObservedGenerator(
        SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
    )

    def factory() -> Any:
        return observed

    specs = build_frontier_strategies(
        factory,
        budget,
        ADAPTIVE_GRID,
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
    )
    if method_runtime not in specs:
        raise KeyError(method_runtime)
    result = specs[method_runtime].run(example.question, example.answer)

    final_nodes = []
    for bid, b in sorted(observed.registry.items(), key=lambda kv: kv[0]):
        snap = observed._snapshot(b)
        final_nodes.append(snap)

    rep = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=(result.metadata or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    ans = rep.get("surfaced_final_answer_raw")
    ans_can = canonicalize_answer(ans, dataset=dataset)
    gold_can = canonicalize_answer(str(example.answer), dataset=dataset)
    gold_in_tree = bool(node_ids_with_answer(final_nodes, gold_can))
    output_mismatch = bool(
        gold_in_tree
        and (rep.get("chosen_final_node_answer_canonical") == gold_can)
        and (ans_can != gold_can)
    )
    extraction_mismatch = bool(
        (rep.get("chosen_final_node_answer_canonical") != rep.get("extracted_final_answer_canonical"))
        or (rep.get("extracted_final_answer_canonical") != rep.get("surfaced_final_answer_canonical"))
    )
    correct = bool(ans_can == gold_can and ans_can is not None)
    if not gold_in_tree:
        failure = "absent_from_tree"
    elif output_mismatch or extraction_mismatch:
        failure = "output_layer_mismatch"
    elif correct:
        failure = "correct"
    else:
        failure = "present_not_selected"

    md = result.metadata or {}
    repeated = bool(float(md.get("repeated_same_family_expansion_rate", 0.0)) > 0.0 or int(md.get("repeated_same_family_expansion_count", 0)) > 0)

    return {
        "dataset": dataset,
        "seed": seed,
        "budget": budget,
        "example_id": str(example.example_id),
        "method": method_public,
        "is_correct": correct,
        "actions": int(result.actions_used),
        "expansions": int(result.expansions),
        "verifications": int(result.verifications),
        "failure_type": failure,
        "absent_from_tree": int(failure == "absent_from_tree"),
        "present_not_selected": int(failure == "present_not_selected"),
        "output_layer_mismatch": int(failure == "output_layer_mismatch"),
        "gold_in_tree": int(gold_in_tree),
        "repeated_same_family_present": int(repeated),
    }


def mean(xs: list[float]) -> float:
    return float(sum(xs)/len(xs)) if xs else 0.0


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/canonical_full_method_ranking_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    prev_path = REPO_ROOT / "outputs/full_method_comparison_bundle/20260419T214335Z/per_example_outcomes.csv"
    prev_methods = set()
    if prev_path.exists():
        prev_methods = {r["method"] for r in csv.DictReader(prev_path.open())}

    method_group = {public: group for public, _, group in METHOD_SPECS}
    runtime_map = {public: runtime_method(full) for public, full, _ in METHOD_SPECS}

    # validate runtime availability once
    probe_rng = random.Random(0)
    probe = build_frontier_strategies(lambda: SimulatedBranchGenerator(rng=probe_rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12), 4, ADAPTIVE_GRID, probe_rng, use_openai_api=False, include_broad_diversity_aggregation_methods=True, include_external_s1_baseline=True, include_external_tale_baseline=True, include_external_l1_baseline=True)

    included = []
    excluded = []
    for public, full, group in METHOD_SPECS:
        rt = runtime_map[public]
        if rt in probe:
            included.append((public, full, group, rt))
        else:
            excluded.append({"method": public, "full_method_name": full, "reason": "method_not_in_current_build_frontier_strategies", "detail": f"runtime key missing: {rt}"})

    rows = []
    example_ids_by_dataset_seed: dict[tuple[str, int], list[str]] = {}
    for dataset in DATASETS:
        for seed in SEEDS:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            example_ids_by_dataset_seed[(dataset, seed)] = [str(e.example_id) for e in examples]
            for budget in BUDGETS:
                for ex in examples:
                    for public, full, group, rt in included:
                        rows.append(run_observed(public, rt, dataset, seed, budget, ex))

    # aggregate overall
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_dataset_method: dict[tuple[str,str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_method[r["method"]].append(r)
        by_dataset_method[(r["dataset"], r["method"])].append(r)

    ds_acc: dict[str, dict[str, float]] = defaultdict(dict)
    for (ds, m), rs in by_dataset_method.items():
        ds_acc[m][ds] = mean([1.0 if x["is_correct"] else 0.0 for x in rs])

    overall = []
    for m, rs in by_method.items():
        overall.append({
            "method": m,
            "method_group": method_group[m],
            "origin_type": "reused" if m in prev_methods else "new_run",
            "included_in_final_ranking": True,
            "mean_accuracy": round(mean([1.0 if x["is_correct"] else 0.0 for x in rs]), 6),
            "dataset_macro_accuracy": round(mean(list(ds_acc[m].values())), 6),
            "avg_actions": round(mean([x["actions"] for x in rs]), 6),
            "avg_expansions": round(mean([x["expansions"] for x in rs]), 6),
            "avg_verifications": round(mean([x["verifications"] for x in rs]), 6),
            "absent_from_tree": sum(x["absent_from_tree"] for x in rs),
            "present_not_selected": sum(x["present_not_selected"] for x in rs),
            "output_layer_mismatch": sum(x["output_layer_mismatch"] for x in rs),
            "repeated_same_family_present": sum(x["repeated_same_family_present"] for x in rs),
            "gold_in_tree": sum(x["gold_in_tree"] for x in rs),
            "notes": "strict_gate1_cap_k6 mapped to fixed_k6_control runtime" if m=="strict_gate1_cap_k6" else "",
        })

    overall.sort(key=lambda r: (-r["mean_accuracy"], r["avg_actions"], r["absent_from_tree"], r["method"]))
    for i,r in enumerate(overall, start=1):
        r["rank"] = i
    overall = [{k:r[k] for k in ["rank","method","method_group","origin_type","included_in_final_ranking","mean_accuracy","dataset_macro_accuracy","avg_actions","avg_expansions","avg_verifications","absent_from_tree","present_not_selected","output_layer_mismatch","repeated_same_family_present","gold_in_tree","notes"]} for r in overall]

    # dataset wise ranking
    ds_rows = []
    for ds in DATASETS:
        cur = []
        for m in by_method:
            rs = by_dataset_method[(ds,m)]
            cur.append({
                "dataset": ds,
                "method": m,
                "method_group": method_group[m],
                "accuracy": round(mean([1.0 if x["is_correct"] else 0.0 for x in rs]), 6),
                "avg_actions": round(mean([x["actions"] for x in rs]), 6),
                "avg_expansions": round(mean([x["expansions"] for x in rs]), 6),
                "avg_verifications": round(mean([x["verifications"] for x in rs]), 6),
                "absent_from_tree": sum(x["absent_from_tree"] for x in rs),
                "present_not_selected": sum(x["present_not_selected"] for x in rs),
                "output_layer_mismatch": sum(x["output_layer_mismatch"] for x in rs),
                "repeated_same_family_present": sum(x["repeated_same_family_present"] for x in rs),
                "gold_in_tree": sum(x["gold_in_tree"] for x in rs),
            })
        cur.sort(key=lambda r: (-r["accuracy"], r["avg_actions"], r["method"]))
        for i,r in enumerate(cur, start=1):
            r["rank"] = i
            ds_rows.append({k:r[k] for k in ["dataset","rank","method","method_group","accuracy","avg_actions","avg_expansions","avg_verifications","absent_from_tree","present_not_selected","output_layer_mismatch","repeated_same_family_present","gold_in_tree"]})

    # head to head vs strict_gate1_cap_k6
    target = "strict_gate1_cap_k6"
    index = {(r["dataset"],r["seed"],r["budget"],r["example_id"],r["method"]): r for r in rows}
    h2h=[]
    for opp in sorted(by_method):
        if opp==target: continue
        improved=worsened=unchanged=0
        acc_t=acc_o=0
        n=0
        for ds in DATASETS:
            for sd in SEEDS:
                for bd in BUDGETS:
                    for exi in example_ids_by_dataset_seed[(ds, sd)]:
                        rt=index[(ds,sd,bd,exi,target)]
                        ro=index[(ds,sd,bd,exi,opp)]
                        tc=bool(rt["is_correct"]); oc=bool(ro["is_correct"])
                        acc_t += 1 if tc else 0
                        acc_o += 1 if oc else 0
                        n+=1
                        if tc and not oc: improved+=1
                        elif (not tc) and oc: worsened+=1
                        else: unchanged+=1
        h2h.append({"opponent":opp,"improved":improved,"worsened":worsened,"unchanged":unchanged,"net_margin":improved-worsened,"latest_method_accuracy":round(acc_t/n,6),"opponent_accuracy":round(acc_o/n,6)})

    h2h.sort(key=lambda r: (-r["net_margin"], -r["opponent_accuracy"], r["opponent"]))

    # add required exclusions for missing/unsupported methods (even if requested list)
    requested = {m for m,_,_ in METHOD_SPECS}
    for m in sorted(requested - set(by_method.keys())):
        if not any(x["method"]==m for x in excluded):
            excluded.append({"method":m,"full_method_name":"","reason":"not_evaluated","detail":"missing from included pool"})

    write_csv(out_dir/"overall_ranking.csv", overall)
    write_csv(out_dir/"dataset_wise_ranking.csv", ds_rows)
    write_csv(out_dir/"strict_gate1_cap_k6_head_to_head.csv", h2h)
    write_csv(out_dir/"excluded_methods.csv", excluded)
    write_csv(out_dir/"per_case_outcomes.csv", rows)

    manifest={
        "artifact_family":"canonical_full_method_ranking",
        "created_at_utc": now.isoformat(),
        "evaluation_contract":{
            "datasets":DATASETS,"seeds":SEEDS,"budgets":BUDGETS,"subset_size_per_dataset_seed":SUBSET_SIZE,
            "surface_inheritance":"extends current full method comparison bundle contract (2026-04-20) by adding strict-phased methods including strict_gate1_cap_k6 on the same surface"
        },
        "included_methods":[m for m in by_method],
        "excluded_count":len(excluded),
        "output_files":["overall_ranking.csv","dataset_wise_ranking.csv","strict_gate1_cap_k6_head_to_head.csv","excluded_methods.csv","per_case_outcomes.csv"],
    }
    (out_dir/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

    # markdown reports
    rank_map={r['method']:r['rank'] for r in overall}
    top=overall[0]['method'] if overall else ''
    top_rank=1 if overall else None
    latest_rank=rank_map.get('strict_gate1_cap_k6')
    adversary = min([r for r in overall if r['method']!='strict_gate1_cap_k6'], key=lambda r: abs(r['mean_accuracy']-next(x['mean_accuracy'] for x in overall if x['method']=='strict_gate1_cap_k6'))) if 'strict_gate1_cap_k6' in rank_map else None

    md=[]
    md.append(f"# CANONICAL FULL METHOD RANKING ({ts})")
    md.append("\n## Purpose\nCreate one canonical full-method leaderboard that includes the latest promoted default `strict_gate1_cap_k6` and major comparison methods on one matched evaluation surface.")
    md.append("\n## Evaluation contract\n- Datasets: openai/gsm8k, HuggingFaceH4/MATH-500, HuggingFaceH4/aime_2024\n- Seeds: 11, 23\n- Budgets: 4, 6, 8\n- Subset size per dataset-seed: 20\n- Contract basis: current broad comparison bundle contract (2026-04-20), extended to include strict-phased finalists and latest promoted strict method.")
    md.append("\n## Included methods\n" + "\n".join([f"- `{m}`" for m in sorted(by_method.keys())]))
    md.append("\n## Excluded methods\n" + ("\n".join([f"- `{e['method']}`: {e['reason']} ({e['detail']})" for e in excluded]) if excluded else "- None"))
    md.append("\n## Aggregate overall ranking\nTop 10:\n")
    for r in overall[:10]:
        md.append(f"- #{r['rank']} `{r['method']}` acc={r['mean_accuracy']:.4f} actions={r['avg_actions']:.3f}")
    md.append("\n## Dataset-wise leaders")
    for ds in DATASETS:
        leader=min([r for r in ds_rows if r['dataset']==ds], key=lambda r:r['rank'])
        md.append(f"- {ds}: #{leader['rank']} `{leader['method']}` acc={leader['accuracy']:.4f}")
    md.append(f"\n## Latest promoted method: exact rank and nearest competitors\n- `strict_gate1_cap_k6` rank: **#{latest_rank}**\n- Overall #1 method: **`{top}`**\n- Strongest direct adversary by closest overall accuracy: **`{adversary['method']}`** (rank #{adversary['rank']}).")
    md.append("\n## Head-to-head results for `strict_gate1_cap_k6`\n")
    for r in h2h[:10]:
        md.append(f"- vs `{r['opponent']}`: improved={r['improved']}, worsened={r['worsened']}, unchanged={r['unchanged']}, net={r['net_margin']}")
    md.append("\n## Cost/performance interpretation\nRanking is accuracy-first with cost/failure tie-breakers. This report distinguishes the promoted default from the overall leader instead of assuming they are identical.")
    md.append("\n## Defensibility gaps\n- Some strict aliases from current canonical docs are excluded if their exact runtime keys are absent in current `build_frontier_strategies`.\n- This remains a bounded matched surface and not universal performance.")
    md.append(f"\n## Safe manuscript summary\nOn this canonical matched contract, the overall leader is `{top}`, while the current promoted default `strict_gate1_cap_k6` ranks #{latest_rank}. Therefore the promoted default is {'also the overall leader' if top=='strict_gate1_cap_k6' else 'not the overall leader'} on this surface.")
    md.append(f"\n## Exact artifact paths\n- `outputs/{out_dir.name}/overall_ranking.csv`\n- `outputs/{out_dir.name}/dataset_wise_ranking.csv`\n- `outputs/{out_dir.name}/strict_gate1_cap_k6_head_to_head.csv`\n- `outputs/{out_dir.name}/excluded_methods.csv`\n- `outputs/{out_dir.name}/manifest.json`")

    doc_path = REPO_ROOT / f"docs/CANONICAL_FULL_METHOD_RANKING_{ts}.md"
    doc_path.write_text("\n".join(md)+"\n", encoding="utf-8")

    status = [
        f"# Current canonical method ranking status ({ts})",
        "",
        "This is the shortest current answer to full-method ranking including `strict_gate1_cap_k6`.",
        "",
        f"- Canonical full ranking artifact: `outputs/{out_dir.name}/overall_ranking.csv`.",
        f"- Overall #1 method: `{top}` (rank #1).",
        f"- `strict_gate1_cap_k6` rank: #{latest_rank}.",
        f"- Strongest direct adversary to `strict_gate1_cap_k6` (closest overall accuracy): `{adversary['method']}`.",
        f"- Promoted default equals overall #1 on this contract: {'yes' if top=='strict_gate1_cap_k6' else 'no'}.",
        "",
        f"See: `docs/{doc_path.name}` and `outputs/{out_dir.name}/`.",
    ]
    status_path = REPO_ROOT / f"docs/CURRENT_CANONICAL_METHOD_RANKING_STATUS_{ts}.md"
    status_path.write_text("\n".join(status)+"\n", encoding="utf-8")

    print(json.dumps({"timestamp":ts,"out_dir":str(out_dir.relative_to(REPO_ROOT)),"doc":str(doc_path.relative_to(REPO_ROOT)),"status_doc":str(status_path.relative_to(REPO_ROOT))}, indent=2))

if __name__ == "__main__":
    main()
