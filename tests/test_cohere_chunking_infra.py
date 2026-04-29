from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=cwd, text=True, capture_output=True, check=True)


def read_csv(path: Path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_plan_count_and_schema(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    run("scripts/plan_cohere_real_model_chunks.py", "--chunk-plan", str(plan), "--datasets", "d1,d2", "--budgets", "2", "--seeds", "11,13", "--methods", "m1,m2", cwd=Path.cwd())
    rows = read_csv(plan)
    assert len(rows) == 8
    assert list(rows[0].keys()) == ["chunk_id", "dataset", "budget", "seed", "method", "target_scored_per_slice", "status"]


def test_chunk_id_lookup_and_dry_run(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    run("scripts/plan_cohere_real_model_chunks.py", "--chunk-plan", str(plan), "--datasets", "d1", "--budgets", "2", "--seeds", "11", "--methods", "m1", cwd=Path.cwd())
    ok = run("scripts/run_cohere_chunk.py", "--chunk-id", "1", "--chunk-plan", str(plan), "--timestamp", "20260429T000000Z", "--dry-run", cwd=Path.cwd())
    assert "run_cohere_real_model_cost_normalized_validation.py" in ok.stdout
    bad = subprocess.run([sys.executable, "scripts/run_cohere_chunk.py", "--chunk-id", "999", "--chunk-plan", str(plan), "--timestamp", "20260429T000000Z", "--dry-run"], text=True, capture_output=True)
    assert bad.returncode != 0


def test_status_no_outputs_partial_and_completed(tmp_path: Path):
    repo = Path.cwd()
    plan = tmp_path / "plan.csv"
    ts = "20260429T010101Z"
    out = tmp_path / "outputs" / f"cohere_real_model_cost_normalized_validation_{ts}"
    out.mkdir(parents=True)
    run("scripts/plan_cohere_real_model_chunks.py", "--chunk-plan", str(plan), "--datasets", "d1", "--budgets", "2", "--seeds", "11", "--methods", "m1", "--target-scored-per-slice", "3", cwd=repo)

    run("scripts/status_cohere_chunk_progress.py", "--chunk-plan", str(plan), "--timestamp", ts, "--output-root", str(tmp_path / "outputs"), cwd=repo)
    rows = read_csv(out / "chunk_progress_status.csv")
    assert rows[0]["status"] == "planned_not_started"

    with (out / "slice_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["provider", "dataset", "seed", "budget", "method", "scored_examples", "failed_examples", "skipped_examples", "accuracy", "total_tokens", "estimated_cost_usd"])
        w.writeheader(); w.writerow({"provider": "cohere", "dataset": "d1", "seed": "11", "budget": "2", "method": "m1", "scored_examples": "2", "failed_examples": "0", "skipped_examples": "0", "accuracy": "0.5", "total_tokens": "10", "estimated_cost_usd": "0.1"})
    run("scripts/status_cohere_chunk_progress.py", "--chunk-plan", str(plan), "--timestamp", ts, "--output-root", str(tmp_path / "outputs"), cwd=repo)
    assert read_csv(out / "chunk_progress_status.csv")[0]["status"] == "incomplete"

    with (out / "slice_summary.csv").open("a", newline="", encoding="utf-8") as f:
        pass
    with (out / "slice_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["provider", "dataset", "seed", "budget", "method", "scored_examples", "failed_examples", "skipped_examples", "accuracy", "total_tokens", "estimated_cost_usd"])
        w.writeheader(); w.writerow({"provider": "cohere", "dataset": "d1", "seed": "11", "budget": "2", "method": "m1", "scored_examples": "3", "failed_examples": "0", "skipped_examples": "0", "accuracy": "0.5", "total_tokens": "10", "estimated_cost_usd": "0.1"})
    run("scripts/status_cohere_chunk_progress.py", "--chunk-plan", str(plan), "--timestamp", ts, "--output-root", str(tmp_path / "outputs"), cwd=repo)
    assert read_csv(out / "chunk_progress_status.csv")[0]["status"] == "completed"


def test_aggregate_final_only_and_pairwise_and_empty_files(tmp_path: Path):
    repo = Path.cwd()
    plan = tmp_path / "plan.csv"
    ts = "20260429T020202Z"
    outroot = tmp_path / "outputs"
    out = outroot / f"cohere_real_model_cost_normalized_validation_{ts}"
    out.mkdir(parents=True)
    run("scripts/plan_cohere_real_model_chunks.py", "--chunk-plan", str(plan), "--datasets", "d1", "--budgets", "2", "--seeds", "11", "--methods", "m1,direct_reserve_semantic_frontier_v2_thresholded_ordered", "--target-scored-per-slice", "3", cwd=repo)

    with (out / "slice_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["provider", "dataset", "seed", "budget", "method", "scored_examples", "failed_examples", "skipped_examples", "accuracy", "total_tokens", "estimated_cost_usd", "avg_latency_seconds"])
        w.writeheader()
        w.writerow({"provider": "cohere", "dataset": "d1", "seed": "11", "budget": "2", "method": "m1", "scored_examples": "3", "failed_examples": "0", "skipped_examples": "0", "accuracy": "0.7", "total_tokens": "20", "estimated_cost_usd": "0.2", "avg_latency_seconds": "1.1"})
        w.writerow({"provider": "cohere", "dataset": "d1", "seed": "11", "budget": "2", "method": "direct_reserve_semantic_frontier_v2_thresholded_ordered", "scored_examples": "2", "failed_examples": "0", "skipped_examples": "0", "accuracy": "0.6", "total_tokens": "10", "estimated_cost_usd": "0.1", "avg_latency_seconds": "1.0"})
    with (out / "pairwise_comparisons.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["provider", "dataset", "seed", "budget", "method_a", "method_b", "accuracy_delta_a_minus_b", "n_paired_examples"])
        w.writeheader()
        w.writerow({"provider": "cohere", "dataset": "d1", "seed": "11", "budget": "2", "method_a": "m1", "method_b": "external_l1_max", "accuracy_delta_a_minus_b": "0.1", "n_paired_examples": "3"})

    run("scripts/status_cohere_chunk_progress.py", "--chunk-plan", str(plan), "--timestamp", ts, "--output-root", str(outroot), cwd=repo)
    status_rows = read_csv(out / "chunk_progress_status.csv")
    thresh = [r for r in status_rows if r["method"] == "direct_reserve_semantic_frontier_v2_thresholded_ordered"][0]
    assert thresh["status"] == "incomplete"
    m1 = [r for r in status_rows if r["method"] == "m1"][0]
    assert m1["pairwise_vs_external_l1_max_available"] == "yes"

    run("scripts/aggregate_cohere_chunks.py", "--chunk-plan", str(plan), "--timestamp", ts, "--output-root", str(outroot), cwd=repo)
    method_rows = read_csv(out / "codex_method_summary_final_only.csv")
    assert [r["method"] for r in method_rows] == ["m1"]
    pair_rows = read_csv(out / "codex_pairwise_vs_external_l1_max.csv")
    assert pair_rows[0]["ci95_status"].startswith("unavailable") and pair_rows[0]["ci95_lo"] == ""


def test_chunk_accumulation_via_summarize_rebuild(tmp_path: Path):
    repo = Path.cwd()
    plan = tmp_path / "plan.csv"
    ts = "20260429T030303Z"
    outroot = tmp_path / "outputs"
    run("scripts/plan_cohere_real_model_chunks.py", "--chunk-plan", str(plan), "--datasets", "d1", "--budgets", "2", "--seeds", "11", "--methods", "m1,m2", "--target-scored-per-slice", "1", cwd=repo)

    fake_runner = tmp_path / "fake_runner.py"
    fake_runner.write_text("""
import argparse, json, csv
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--timestamp',required=True);p.add_argument('--output-root',default='outputs')
p.add_argument('--datasets');p.add_argument('--budgets');p.add_argument('--seeds');p.add_argument('--methods');p.add_argument('--summarize-only',action='store_true')
a,_=p.parse_known_args()
out=Path(a.output_root)/f'cohere_real_model_cost_normalized_validation_{a.timestamp}'
out.mkdir(parents=True,exist_ok=True)
per=out/'per_example_records.jsonl'
if not a.summarize_only:
 r={'provider':'cohere','dataset':a.datasets,'seed':int(a.seeds.split(',')[0]),'budget':int(a.budgets.split(',')[0]),'method':a.methods,'example_id':'e1','scored':1,'exact_match':1,'failed':0,'skipped':0,'attempted':1,'retry_attempts':0,'input_tokens':1,'output_tokens':1,'total_tokens':2,'latency_seconds':0.1,'estimated_cost_usd':0.01}
 with per.open('a',encoding='utf-8') as f:f.write(json.dumps(r)+'\\n')
rows=[json.loads(x) for x in per.open(encoding='utf-8')] if per.exists() else []
by={}
for r in rows:by[(r['provider'],r['dataset'],str(r['seed']),str(r['budget']),r['method'])]=r
with (out/'slice_summary.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=['provider','dataset','seed','budget','method','successfully_scored_examples','failed_examples','skipped_examples','accuracy','total_tokens','estimated_dollar_cost']);w.writeheader()
 for (pr,d,s,b,m),r in by.items():w.writerow({'provider':pr,'dataset':d,'seed':s,'budget':b,'method':m,'successfully_scored_examples':1,'failed_examples':0,'skipped_examples':0,'accuracy':1.0,'total_tokens':2,'estimated_dollar_cost':0.01})
with (out/'pairwise_comparisons.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=['provider','dataset','seed','budget','method_a','method_b','accuracy_delta_a_minus_b','n_paired_examples']);w.writeheader()
""",encoding='utf-8')

    run("scripts/run_cohere_chunk.py", "--chunk-id", "1", "--chunk-plan", str(plan), "--timestamp", ts, "--output-root", str(outroot), "--runner-script", str(fake_runner), cwd=repo)
    run("scripts/run_cohere_chunk.py", "--chunk-id", "2", "--chunk-plan", str(plan), "--timestamp", ts, "--output-root", str(outroot), "--runner-script", str(fake_runner), cwd=repo)
    run("scripts/status_cohere_chunk_progress.py", "--chunk-plan", str(plan), "--timestamp", ts, "--output-root", str(outroot), cwd=repo)
    run("scripts/aggregate_cohere_chunks.py", "--chunk-plan", str(plan), "--timestamp", ts, "--output-root", str(outroot), cwd=repo)

    out = outroot / f"cohere_real_model_cost_normalized_validation_{ts}"
    status = read_csv(out / "chunk_progress_status.csv")
    assert len([r for r in status if r['status']=='completed']) == 2
    slices = read_csv(out / "slice_summary.csv")
    assert len(slices) == 2


def test_compact_ledger_export_and_rebuild_without_raw_jsonl(tmp_path: Path):
    repo = Path.cwd()
    ts = "20260429T040404Z"
    outroot = tmp_path / "outputs"
    out = outroot / f"cohere_real_model_cost_normalized_validation_{ts}"
    out.mkdir(parents=True)
    per = out / "per_example_records.jsonl"
    per.write_text(
        '{"provider":"cohere","dataset":"d1","seed":11,"budget":2,"method":"m1","example_id":"e1","status":"scored","exact_match":1,"attempted":1,"scored":1,"failed":0,"skipped":0,"retry_attempts":0,"input_tokens":1,"output_tokens":1,"total_tokens":2,"latency_seconds":0.1,"estimated_cost_usd":0.01}\n'
        '{"provider":"cohere","dataset":"d1","seed":11,"budget":2,"method":"external_l1_max","example_id":"e1","status":"scored","exact_match":0,"attempted":1,"scored":1,"failed":0,"skipped":0,"retry_attempts":0,"input_tokens":1,"output_tokens":1,"total_tokens":2,"latency_seconds":0.1,"estimated_cost_usd":0.01}\n',
        encoding="utf-8",
    )
    run("scripts/export_compact_cohere_ledger.py", "--timestamp", ts, "--output-root", str(outroot), cwd=repo)
    assert (out / "compact_per_example_ledger.csv").exists()
    per.unlink()  # simulate fresh checkout without raw ledger

    plan = tmp_path / "plan.csv"
    run("scripts/plan_cohere_real_model_chunks.py", "--chunk-plan", str(plan), "--datasets", "d1", "--budgets", "2", "--seeds", "11", "--methods", "m1,external_l1_max", "--target-scored-per-slice", "1", cwd=repo)
    run("scripts/status_cohere_chunk_progress.py", "--chunk-plan", str(plan), "--timestamp", ts, "--output-root", str(outroot), cwd=repo)
    run("scripts/aggregate_cohere_chunks.py", "--chunk-plan", str(plan), "--timestamp", ts, "--output-root", str(outroot), cwd=repo)
    status = read_csv(out / "chunk_progress_status.csv")
    assert len([r for r in status if r["status"] == "completed"]) == 2
