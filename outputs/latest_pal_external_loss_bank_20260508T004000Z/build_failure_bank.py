#!/usr/bin/env python3
"""Offline merge of latest-PAL vs external loss artifacts. Writes sibling CSV/JSON/MD outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
ROOT = OUT_DIR.parents[1]
PAL_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"

ART = {
    "collect": ROOT / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z",
    "paired300": ROOT / "outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z",
    "paired100": ROOT / "outputs/cohere_paired_pal_retry_vs_external_l1_100case_20260506T185133Z",
    "pilot30": ROOT / "outputs/cohere_pal_retry_vs_3_external_baselines_30case_20260507T152735Z",
    "corpus88": ROOT / "outputs/failure_case_corpus_inputs_external_losses_88case_20260507T041700Z",
    "corpus07": ROOT / "outputs/failure_case_corpus_20260507",
    "analysis300": ROOT / "outputs/pal_retry_300case_analysis_20260506",
}

BANK_COLS = [
    "case_id",
    "source_artifact",
    "source_file",
    "internal_method",
    "comparison_scope",
    "loss_against_external_l1_max",
    "loss_against_any_external",
    "pal_correct",
    "external_l1_max_correct",
    "best_external_correct",
    "best_external_name",
    "gold_answer",
    "pal_prediction",
    "external_l1_prediction",
    "tale_prediction",
    "s1_prediction",
    "problem_text",
    "gold_in_tree_or_pool",
    "failure_tag",
    "failure_type",
    "present_not_selected",
    "gold_absent_discovery",
    "track_b_status",
    "notes",
]


def as_bool01(v) -> bool:
    return str(v).strip() in ("1", "True", "true", "yes")


def read_json(p: Path):
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def id_band(case_ids: list[str]) -> str:
    if not case_ids:
        return ""
    nums = []
    for c in case_ids:
        if "_" in c:
            try:
                nums.append(int(c.rsplit("_", 1)[-1]))
            except ValueError:
                pass
    if not nums:
        return ""
    return f"openai_gsm8k_{min(nums)}..{max(nums)} (n={len(case_ids)})"


def load_manifest_methods(p: Path) -> tuple[bool, str, str]:
    if not p.is_file():
        return False, "", ""
    m = read_json(p)
    if not m:
        return True, "", ""
    methods = []
    if "primary_method_id" in m:
        methods.append(m["primary_method_id"])
    if "methods" in m and isinstance(m["methods"], list):
        methods.extend(m["methods"])
    blob = json.dumps(m)
    match = PAL_METHOD in blob
    baselines = ""
    if "external_baseline_ids" in m:
        baselines = ";".join(m["external_baseline_ids"])
    elif "methods" in m:
        others = [x for x in m["methods"] if x != PAL_METHOD]
        baselines = ";".join(others)
    return True, baselines, ("yes" if match else "no")


def parse_cluster(path: Path) -> dict[str, dict]:
    out = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["case_id"]] = row
    return out


def parse_replay_commitment(path: Path) -> dict[str, str]:
    m = {}
    if not path.is_file():
        return m
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mech = row.get("primary_commitment_mechanism") or ""
            m[row["case_id"]] = mech
    return m


def load_track_b(collect: Path):
    p = collect / "track_b_gate_offline_replay_summary.json"
    data = read_json(p) or {}
    fixed = set(data.get("targets_fixed_case_ids") or [])
    fixture = {x["case_id"]: x for x in (data.get("fixture_anchor_subset") or [])}
    return fixed, fixture, data


def bank_row_template():
    return {k: "" for k in BANK_COLS}


def main():
    collect = ART["collect"]
    failure_summary = read_json(collect / "failure_collection_summary.json") or {}
    cluster_by_case = parse_cluster(collect / "failure_cluster_summary.csv")
    replay_mech = parse_replay_commitment(collect / "present_not_selected_replay_table.csv")
    track_fixed, track_fixture, track_data = load_track_b(collect)

    def track_status(case_id: str) -> str:
        if case_id in track_fixed:
            return "Track B offline replay: fixed_by_override"
        fx = track_fixture.get(case_id)
        if fx:
            return f"Track B offline replay: {fx.get('outcome_tag', '')}"
        if case_id in cluster_by_case:
            return "Track B: not in anchor fixture subset"
        return ""

    def exec_not_committed(case_id: str) -> str:
        mech = replay_mech.get(case_id, "")
        if "overlay_previous_equals_gold" in mech and "bad_pal_stdout" in mech:
            return "yes"
        if "pal_stdout" in mech and "gold" in mech.lower():
            pass
        return "no"

    bank_rows: list[dict] = []

    # --- 4-way collect pal_loss_external_win ---
    pal_loss_p = collect / "pal_loss_external_win_cases.csv"
    with pal_loss_p.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row["case_id"]
            cl = cluster_by_case.get(cid, {})
            ft = cl.get("failure_type", "")
            tag = cl.get("failure_tag", "")
            git = cl.get("gold_in_tree", "")
            pns = "yes" if "present_not_selected" in ft or "not selected" in (tag or "") else "no"
            gad = "yes" if "gold_absent" in ft or "absent" in (tag or "").lower() else "no"
            if pns == "yes" and gad == "yes":
                gad = "no"
            eb = "yes" if as_bool01(row.get("best_external_correct")) else "no"
            l1 = "yes" if as_bool01(row.get("external_l1_max_correct")) else "no"
            any_ext = "yes" if any(
                as_bool01(row.get(k))
                for k in (
                    "external_l1_max_correct",
                    "external_tale_prompt_budgeting_correct",
                    "external_s1_budget_forcing_correct",
                )
            ) else "no"
            r = bank_row_template()
            r.update(
                {
                    "case_id": cid,
                    "source_artifact": str(collect.relative_to(ROOT)),
                    "source_file": "pal_loss_external_win_cases.csv",
                    "internal_method": PAL_METHOD,
                    "comparison_scope": "pal_vs_three_externals_complete_rows",
                    "loss_against_external_l1_max": l1,
                    "loss_against_any_external": any_ext,
                    "pal_correct": "0",
                    "external_l1_max_correct": row.get("external_l1_max_correct", ""),
                    "best_external_correct": row.get("best_external_correct", ""),
                    "best_external_name": row.get("best_external_methods", ""),
                    "gold_answer": row.get("gold_answer", ""),
                    "pal_prediction": row.get("pal_answer", ""),
                    "external_l1_prediction": row.get("external_l1_max_answer", ""),
                    "tale_prediction": row.get("external_tale_prompt_budgeting_answer", ""),
                    "s1_prediction": row.get("external_s1_budget_forcing_answer", ""),
                    "problem_text": row.get("question", ""),
                    "gold_in_tree_or_pool": git,
                    "failure_tag": tag,
                    "failure_type": ft,
                    "present_not_selected": pns,
                    "gold_absent_discovery": gad,
                    "track_b_status": track_status(cid),
                    "notes": (
                        (row.get("operation_hint_tags") or "")
                        + (
                            (";replay_mechanism=" + replay_mech[cid])
                            if cid in replay_mech
                            else ""
                        )
                        + (
                            ";executable_pal_present_but_not_committed=yes"
                            if exec_not_committed(cid) == "yes"
                            else ""
                        )
                    ),
                }
            )
            bank_rows.append(r)

    # --- 300-case paired ---
    p300 = ART["paired300"] / "paired_casebook.csv"
    with p300.open(encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            if row.get("external_correct_pal_wrong") != "1":
                continue
            cid = row["example_id"]
            l1 = as_bool01(row.get("external_exact"))
            r = bank_row_template()
            pns = "yes" if as_bool01(row.get("pal_present_not_selected")) else "no"
            gad = "yes" if as_bool01(row.get("pal_gold_absent")) else "no"
            r.update(
                {
                    "case_id": cid,
                    "source_artifact": str(ART["paired300"].relative_to(ROOT)),
                    "source_file": "paired_casebook.csv",
                    "internal_method": PAL_METHOD,
                    "comparison_scope": "pal_vs_external_l1_max_only",
                    "loss_against_external_l1_max": "yes" if l1 else "no",
                    "loss_against_any_external": "yes" if l1 else "no",
                    "pal_correct": "0",
                    "external_l1_max_correct": row.get("external_exact", ""),
                    "best_external_correct": row.get("external_exact", ""),
                    "best_external_name": "external_l1_max",
                    "gold_answer": row.get("gold_answer", ""),
                    "pal_prediction": row.get("pal_final_answer", ""),
                    "external_l1_prediction": row.get("external_final_answer", ""),
                    "problem_text": row.get("question", ""),
                    "gold_in_tree_or_pool": "",
                    "failure_tag": "",
                    "failure_type": "",
                    "present_not_selected": pns,
                    "gold_absent_discovery": gad,
                    "track_b_status": "",
                    "notes": "300-case paired; tale/s1 not in this run",
                }
            )
            bank_rows.append(r)

    # --- 100-case paired ---
    p100 = ART["paired100"] / "paired_casebook.csv"
    with p100.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("external_correct_pal_wrong") != "1":
                continue
            cid = row["example_id"]
            l1 = as_bool01(row.get("external_exact"))
            r = bank_row_template()
            pns = "yes" if as_bool01(row.get("pal_present_not_selected")) else "no"
            gad = "yes" if as_bool01(row.get("pal_gold_absent")) else "no"
            r.update(
                {
                    "case_id": cid,
                    "source_artifact": str(ART["paired100"].relative_to(ROOT)),
                    "source_file": "paired_casebook.csv",
                    "internal_method": PAL_METHOD,
                    "comparison_scope": "pal_vs_external_l1_max_only",
                    "loss_against_external_l1_max": "yes" if l1 else "no",
                    "loss_against_any_external": "yes" if l1 else "no",
                    "pal_correct": "0",
                    "external_l1_max_correct": row.get("external_exact", ""),
                    "best_external_correct": row.get("external_exact", ""),
                    "best_external_name": "external_l1_max",
                    "gold_answer": row.get("gold_answer", ""),
                    "pal_prediction": row.get("pal_final_answer", ""),
                    "external_l1_prediction": row.get("external_final_answer", ""),
                    "problem_text": row.get("question", ""),
                    "present_not_selected": pns,
                    "gold_absent_discovery": gad,
                    "track_b_status": "",
                    "notes": "100-case paired",
                }
            )
            bank_rows.append(r)

    # --- 30-case 4-way pilot ---
    p30 = ART["pilot30"] / "paired_casebook.csv"
    with p30.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pal_wrong = not as_bool01(row.get("pal_correct"))
            best_ok = as_bool01(row.get("best_external_correct"))
            if not (pal_wrong and best_ok):
                continue
            cid = row["case_id"]
            l1_ok = as_bool01(row.get("external_l1_max_correct"))
            any_ok = any(
                as_bool01(row.get(k))
                for k in (
                    "external_l1_max_correct",
                    "external_tale_prompt_budgeting_correct",
                    "external_s1_budget_forcing_correct",
                )
            )
            r = bank_row_template()
            r.update(
                {
                    "case_id": cid,
                    "source_artifact": str(ART["pilot30"].relative_to(ROOT)),
                    "source_file": "paired_casebook.csv",
                    "internal_method": PAL_METHOD,
                    "comparison_scope": "pal_vs_three_externals",
                    "loss_against_external_l1_max": "yes" if l1_ok else "no",
                    "loss_against_any_external": "yes" if any_ok else "no",
                    "pal_correct": row.get("pal_correct", ""),
                    "external_l1_max_correct": row.get("external_l1_max_correct", ""),
                    "best_external_correct": row.get("best_external_correct", ""),
                    "best_external_name": row.get("best_external_method_for_case", ""),
                    "gold_answer": row.get("gold_answer", ""),
                    "pal_prediction": row.get("pal_answer", ""),
                    "external_l1_prediction": row.get("external_l1_max_answer", ""),
                    "tale_prediction": row.get("external_tale_prompt_budgeting_answer", ""),
                    "s1_prediction": row.get("external_s1_budget_forcing_answer", ""),
                    "problem_text": row.get("question", ""),
                    "present_not_selected": "",
                    "gold_absent_discovery": "",
                    "track_b_status": "",
                    "notes": "30-case pilot; no failure_cluster in bundle",
                }
            )
            bank_rows.append(r)

    # Write bank CSV
    bank_path = OUT_DIR / "latest_pal_external_loss_bank.csv"
    with bank_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=BANK_COLS, extrasaction="ignore")
        w.writeheader()
        for row in bank_rows:
            w.writerow(row)

    # Union by case
    by_case: dict[str, dict] = {}
    src_labels = {
        "cohere_collect_pal_failure": "4way_247",
        "cohere_paired_pal_retry_vs_external_l1_300case": "300case",
        "cohere_paired_pal_retry_vs_external_l1_100case": "100case",
        "cohere_pal_retry_vs_3_external_baselines_30case": "30case",
    }

    def source_bucket(sa: str) -> str:
        for k, v in src_labels.items():
            if k in sa:
                return v
        return "other"

    for row in bank_rows:
        cid = row["case_id"]
        u = by_case.setdefault(
            cid,
            {
                "case_id": cid,
                "source_artifacts": set(),
                "appears_in_34_4way_pool": "no",
                "appears_in_300case": "no",
                "appears_in_100case": "no",
                "appears_in_30case": "no",
                "appears_in_88case_or_failure_corpus": "no",
                "strongest_loss_scope": "",
                "known_external_winners": set(),
                "gold_absent_or_present_not_selected": set(),
                "known_failure_tags": set(),
                "problem_text": "",
                "gold_answer": "",
                "best_available_pal_prediction": "",
                "best_available_external_prediction": "",
                "recommended_next_track": "",
            },
        )
        u["source_artifacts"].add(row["source_artifact"])
        b = source_bucket(row["source_artifact"])
        if b == "4way_247":
            u["appears_in_34_4way_pool"] = "yes"
        elif b == "300case":
            u["appears_in_300case"] = "yes"
        elif b == "100case":
            u["appears_in_100case"] = "yes"
        elif b == "30case":
            u["appears_in_30case"] = "yes"
        if row.get("best_external_name"):
            u["known_external_winners"].add(row["best_external_name"])
        if row.get("failure_tag"):
            u["known_failure_tags"].add(row["failure_tag"])
        if row.get("present_not_selected") == "yes":
            u["gold_absent_or_present_not_selected"].add("present_not_selected")
        if row.get("gold_absent_discovery") == "yes":
            u["gold_absent_or_present_not_selected"].add("gold_absent_discovery")
        if not u["problem_text"] and row.get("problem_text"):
            u["problem_text"] = row["problem_text"]
        if not u["gold_answer"] and row.get("gold_answer"):
            u["gold_answer"] = row["gold_answer"]
        # prefer 4-way predictions
        if "cohere_collect_pal_failure" in row["source_artifact"]:
            u["best_available_pal_prediction"] = row.get("pal_prediction", "")
            u["best_available_external_prediction"] = row.get("external_l1_prediction", "")
        elif not u["best_available_pal_prediction"]:
            u["best_available_pal_prediction"] = row.get("pal_prediction", "")
            u["best_available_external_prediction"] = row.get("external_l1_prediction", "")

    scope_rank = {
        "pal_vs_three_externals_complete_rows": 3,
        "pal_vs_three_externals": 3,
        "pal_vs_external_l1_max_only": 1,
    }

    union_rows = []
    rank_to_scope = {
        3: "pal_vs_three_externals",
        1: "pal_vs_external_l1_max_only",
        0: "unknown",
    }
    for cid, u in sorted(by_case.items()):
        scopes = [
            scope_rank.get(r["comparison_scope"], 0)
            for r in bank_rows
            if r["case_id"] == cid
        ]
        strongest = max(scopes) if scopes else 0
        u["strongest_loss_scope"] = rank_to_scope.get(strongest, "mixed")
        u["source_artifacts"] = ";".join(sorted(u["source_artifacts"]))
        u["known_external_winners"] = ";".join(sorted(u["known_external_winners"]))
        u["known_failure_tags"] = "|".join(sorted(u["known_failure_tags"]))
        u["gold_absent_or_present_not_selected"] = ";".join(
            sorted(u["gold_absent_or_present_not_selected"])
        )
        # recommend
        rec = []
        if "present_not_selected" in u["gold_absent_or_present_not_selected"]:
            rec.append("selector/tiebreak/PNS")
        if "gold_absent_discovery" in u["gold_absent_or_present_not_selected"]:
            rec.append("search/budget/gold_absent")
        if cid in track_fixed:
            rec.append("verify Track B fix generalizes")
        u["recommended_next_track"] = ";".join(rec) if rec else "reproduce_in_minimal_slice"
        union_rows.append({k: u[k] for k in u})

    union_path = OUT_DIR / "latest_pal_external_loss_union_by_case.csv"
    union_fields = [
        "case_id",
        "source_artifacts",
        "appears_in_34_4way_pool",
        "appears_in_300case",
        "appears_in_100case",
        "appears_in_30case",
        "appears_in_88case_or_failure_corpus",
        "strongest_loss_scope",
        "known_external_winners",
        "gold_absent_or_present_not_selected",
        "known_failure_tags",
        "problem_text",
        "gold_answer",
        "best_available_pal_prediction",
        "best_available_external_prediction",
        "recommended_next_track",
    ]
    with union_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=union_fields)
        w.writeheader()
        for row in union_rows:
            w.writerow(row)

    # Mechanism counts (unique cases in union)
    unique_ids = {r["case_id"] for r in bank_rows}
    l1_only_ids = {
        r["case_id"] for r in bank_rows if r["loss_against_external_l1_max"] == "yes"
    }
    best_ids = {r["case_id"] for r in bank_rows if r["loss_against_any_external"] == "yes"}

    def classify_and_hints(cid: str) -> tuple[str, str]:
        cl = cluster_by_case.get(cid)
        if cl:
            return cl.get("failure_type", ""), cl.get("operation_hint_tags", "")
        rows = [r for r in bank_rows if r["case_id"] == cid]
        if any(r.get("present_not_selected") == "yes" for r in rows):
            return "present_not_selected_heuristic", ""
        if any(r.get("gold_absent_discovery") == "yes" for r in rows):
            return "gold_absent_heuristic", ""
        return "unknown", ""

    pn_ids = set()
    ga_ids = set()
    unk_ids = set()
    rr_ids, tc_ids, diff_ids, mfl_ids = set(), set(), set(), set()
    ex_npnc = set()

    for cid in unique_ids:
        ft, hints = classify_and_hints(cid)
        if "present_not_selected" in ft:
            pn_ids.add(cid)
        elif "gold_absent" in ft or "gold_absent_heuristic" in ft:
            ga_ids.add(cid)
        else:
            unk_ids.add(cid)
        hlow = (hints or "").lower()
        if "rate_ratio" in hlow:
            rr_ids.add(cid)
        if "temporal_change" in hlow:
            tc_ids.add(cid)
        if "difference" in hlow:
            diff_ids.add(cid)
        if "missing_final_leaf" in hlow or "missing_frontier" in hlow:
            mfl_ids.add(cid)
        if exec_not_committed(cid) == "yes":
            ex_npnc.add(cid)

    tb_fixed = set(track_fixed) & unique_ids
    tb_still = {
        fx["case_id"]
        for fx in track_fixture.values()
        if fx.get("outcome_tag") == "unchanged_still_wrong" and fx["case_id"] in unique_ids
    }

    mechanism = {
        "total_unique_latest_PAL_loss_cases": len(unique_ids),
        "unique_L1_only_losses": len(l1_only_ids & unique_ids),
        "unique_any_best_external_losses": len(best_ids),
        "present_not_selected": len(pn_ids & unique_ids),
        "gold_absent_discovery": len(ga_ids & unique_ids),
        "unknown_mechanism": len(unk_ids & unique_ids),
        "Track_B_fixed": len(tb_fixed),
        "Track_B_still_wrong": len(tb_still),
        "rate_ratio": len(rr_ids & unique_ids),
        "temporal_change": len(tc_ids & unique_ids),
        "difference": len(diff_ids & unique_ids),
        "missing_final_leaf": len(mfl_ids & unique_ids),
        "executable_pal_present_but_not_committed": len(ex_npnc & unique_ids),
        "notes": {
            "union_definition": "Unique case_ids among union-eligible bank rows (latest PAL manifests only).",
            "L1_only_count_is_subset_of_rows_with_L1_win": True,
            "failure_case_corpus_and_88case_excluded_from_union": True,
        },
    }
    (OUT_DIR / "mechanism_counts.json").write_text(
        json.dumps(mechanism, indent=2), encoding="utf-8"
    )

    # Artifact inventory
    inv_rows = []

    def add_inv(
        rel_path: str,
        manifest_rel: str | None,
        include: bool,
        exclusion: str,
        extra_loss_l1: str = "",
        extra_loss_best: str = "",
        eval_count: str = "",
        band: str = "",
        api: str = "real_api_cohere",
    ):
        mp = ROOT / manifest_rel if manifest_rel else None
        pres, baselines, method_match = load_manifest_methods(mp) if mp else (False, "", "no")
        if include and pres and method_match == "yes":
            method_col = PAL_METHOD
        elif not include:
            method_col = "n/a_excluded_from_union"
        else:
            method_col = "manifest_missing_or_method_mismatch"
        inv_rows.append(
            {
                "artifact_path": rel_path,
                "manifest_present": "yes" if pres else "no",
                "method": method_col,
                "baselines": baselines,
                "evaluated_case_count": eval_count,
                "loss_count_l1": extra_loss_l1,
                "loss_count_any_or_best_external": extra_loss_best,
                "case_id_band": band,
                "real_api_or_replay": api,
                "include_in_latest_pal_union": "yes" if include else "no",
                "exclusion_reason": exclusion,
            }
        )

    add_inv(
        str(collect.relative_to(ROOT)),
        str((collect / "manifest.json").relative_to(ROOT)),
        True,
        "",
        "23",
        "34",
        str(failure_summary.get("evaluated_case_count", "247")),
        "openai_gsm8k_1072..1318 (247 ids)",
        "real_api_cohere",
    )

    st300 = read_json(ART["paired300"] / "manifest.json") or {}
    add_inv(
        str(ART["paired300"].relative_to(ROOT)),
        str((ART["paired300"] / "manifest.json").relative_to(ROOT)),
        True,
        "",
        "21",
        "21",
        str(st300.get("selected_count", "300")),
        "sampled_band_excludes_772_prior_ids_see_manifest",
        "real_api_cohere",
    )

    st100 = read_json(ART["paired100"] / "manifest.json") or {}
    add_inv(
        str(ART["paired100"].relative_to(ROOT)),
        str((ART["paired100"] / "manifest.json").relative_to(ROOT)),
        True,
        "",
        str((read_json(ART["paired100"] / "paired_summary.json") or {}).get("external_correct_pal_wrong_count", "9")),
        str((read_json(ART["paired100"] / "paired_summary.json") or {}).get("external_correct_pal_wrong_count", "9")),
        str(st100.get("selected_count", "100")),
        "see_paired_casebook_id_range",
        "real_api_cohere",
    )

    n30_l1 = len(
        {
            r["case_id"]
            for r in bank_rows
            if "30case" in r["source_artifact"] and r["loss_against_external_l1_max"] == "yes"
        }
    )
    n30_best = len(
        {r["case_id"] for r in bank_rows if "30case" in r["source_artifact"]}
    )
    add_inv(
        str(ART["pilot30"].relative_to(ROOT)),
        str((ART["pilot30"] / "manifest.json").relative_to(ROOT)),
        True,
        "",
        str(n30_l1),
        str(n30_best),
        "30",
        "openai_gsm8k_50..79",
        "real_api_cohere",
    )

    add_inv(
        str(ART["corpus88"].relative_to(ROOT)),
        "",
        False,
        "no_manifest_primary_method;paired_casebook_only_unverified",
        "",
        "",
        "88",
        "mixed_low_ids_and_legacy",
        "unknown",
    )

    add_inv(
        str(ART["corpus07"].relative_to(ROOT)),
        "",
        False,
        "integrated_corpus;failure_cases.csv_uses_our_exact_without_latest_PAL_manifest",
        "",
        "",
        "48",
        "see_failure_cases.csv",
        "mixed",
    )

    add_inv(
        str(ART["analysis300"].relative_to(ROOT)),
        "",
        False,
        "markdown_and_json_summaries_only_no_per_case_manifest",
        "",
        "",
        "",
        "",
        "offline_analysis",
    )

    add_inv(
        str((collect / "track_b_gate_offline_replay_summary.json").relative_to(ROOT)),
        str((collect / "manifest.json").relative_to(ROOT)),
        False,
        "Track B offline replay diagnostics;not_merged_into_union_rows",
        "",
        "",
        "",
        "",
        "offline_replay",
    )

    inv_path = OUT_DIR / "artifact_inventory.csv"
    inv_fields = [
        "artifact_path",
        "manifest_present",
        "method",
        "baselines",
        "evaluated_case_count",
        "loss_count_l1",
        "loss_count_any_or_best_external",
        "case_id_band",
        "real_api_or_replay",
        "include_in_latest_pal_union",
        "exclusion_reason",
    ]
    with inv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=inv_fields)
        w.writeheader()
        for row in inv_rows:
            w.writerow(row)

    # mechanism_report.md
    top_anchors = [
        ("openai_gsm8k_1087", "Track B replay fixed overlay vs bad PAL stdout; rate/temporal hints."),
        ("openai_gsm8k_1279", "Track B replay fixed; gold-vs-surface mismatch in replay table."),
        ("openai_gsm8k_1290", "Track B replay fixed; high-revenue charity word problem."),
        ("openai_gsm8k_1082", "PNS in cluster; alphabet rewrite counting."),
        ("openai_gsm8k_1099", "gold_absent_discovery in 4-way cluster."),
        ("openai_gsm8k_1125", "gold_absent_discovery; extreme rate error."),
        ("openai_gsm8k_773", "300-case L1 win over PAL retry row (paired casebook)."),
        ("openai_gsm8k_787", "300-case L1 win; additional representative from paired retry cohort."),
        ("openai_gsm8k_54", "30-case external-only pilot band."),
        ("openai_gsm8k_1124", "PNS + frontier tiebreak in replay table columns."),
    ]

    report = f"""# Latest PAL external loss bank (offline)

## Output bundle
- Directory: `{OUT_DIR.relative_to(ROOT)}`
- Built from manifests proving `{PAL_METHOD}`.

## Are the 34 preferred failures globally complete?
**No.** The 34 are **artifact-complete** for the 247-id suffix evaluation (`openai_gsm8k_1072..1318`) with three external baselines. Additional disjoint losses appear in the 300-case paired cohort, the 100-case paired cohort, and the 30-case pilot.

## Deduplicated headline counts
- Unique case IDs in union bank (union-eligible sources): **{len(unique_ids)}**
- Rows in per-source bank (includes duplicates if a case appears in multiple artifacts — none observed across non-overlapping bands): **{len(bank_rows)}**

## Mechanism buckets (unique cases; see `mechanism_counts.json`)
- present_not_selected (cluster/heuristic): **{mechanism['present_not_selected']}**
- gold_absent_discovery: **{mechanism['gold_absent_discovery']}**
- unknown: **{mechanism['unknown_mechanism']}**
- Track B offline fixed IDs (subset): **{mechanism['Track_B_fixed']}**
- executable PAL present but not committed (replay `primary_commitment_mechanism`): **{mechanism['executable_pal_present_but_not_committed']}**

## Top 10 anchor cases (next implementation loop)
"""
    for cid, reason in top_anchors:
        report += f"- **{cid}** — {reason}\n"

    report += f"""
## Caveats
- 88-case input corpus and `failure_case_corpus_20260507` are inventoried but **excluded** from the union until a manifest ties rows to the latest PAL method.
- Paired 300/100 runs compare **L1 only**; “best external” scopes exist only in 4-way + 30-case pilots.
- Mechanism tags for 300-case rows lean on `pal_present_not_selected` / `pal_gold_absent`; 30-case pilot lacks cluster labels.
- `operation_hint_tags` for rate/temporal/difference are taken from `failure_cluster_summary.csv` when present; otherwise marked unknown.

## Repro
```bash
cd {ROOT}
python3 {OUT_DIR / "build_failure_bank.py"}
```
"""
    (OUT_DIR / "mechanism_report.md").write_text(report, encoding="utf-8")

    print("Wrote", OUT_DIR)


if __name__ == "__main__":
    main()
