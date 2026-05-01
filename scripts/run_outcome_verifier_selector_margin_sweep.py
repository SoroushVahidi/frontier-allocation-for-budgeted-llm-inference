#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

def run_margin(input_path: str, score_cache: str, margin: float, out_dir: Path) -> dict:
    cmd = [sys.executable, 'scripts/run_outcome_verifier_answer_group_selector.py', '--input', input_path, '--output-dir', str(out_dir), '--selector-name', 'outcome_verifier_answer_group_selector_v1', '--scorer-mode', 'cached_jsonl', '--score-cache', score_cache, '--min-verifier-margin', str(margin), '--require-trace-for-override', '--dedupe-verifier-items', '--no-gold-features']
    subprocess.check_call(cmd)
    return json.loads((out_dir / 'selector_summary.json').read_text(encoding='utf-8'))


def choose_best_margin(rows: list[dict]) -> dict:
    def rank_key(r: dict):
        return (r['net_fixes_minus_breaks'], -r['breaks'], r['override_precision'], -r['total_overrides'])
    return sorted(rows, key=rank_key, reverse=True)[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--score-cache', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--margins', default='0,0.05,0.10,0.15,0.20,0.30')
    args = ap.parse_args()

    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    per = out / 'per_margin_casebooks'; per.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in [float(x) for x in args.margins.split(',')]:
        m_dir = per / f'margin_{m:.2f}'.replace('.', 'p')
        s = run_margin(args.input, args.score_cache, m, m_dir)
        s['margin'] = m
        rows.append(s)

    best = choose_best_margin(rows)
    summary = {'timestamp': datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'), 'recommended_margin': best['margin'], 'criterion': 'max net fixes, then breaks=0, then precision, then fewer overrides', 'rows': rows}
    (out / 'margin_sweep_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    with (out / 'margin_sweep_summary.csv').open('w', newline='', encoding='utf-8') as f:
        fns = ['margin','total_cases','total_overrides','fixes','breaks','net_fixes_minus_breaks','override_precision','accuracy','current_incumbent_accuracy','oracle_ceiling_on_package','recoverable_trace_terminal_cases','recoveries_among_gold_in_terminal_node_cases','failures_gold_present_in_terminal_nodes_not_chosen']
        w = csv.DictWriter(f, fieldnames=fns); w.writeheader()
        for r in rows:
            w.writerow({
                'margin': r.get('margin'), 'total_cases': r.get('total_cases'), 'total_overrides': r.get('total_overrides'), 'fixes': r.get('fixes'), 'breaks': r.get('breaks'), 'net_fixes_minus_breaks': r.get('net_fixes_minus_breaks'), 'override_precision': r.get('override_precision'), 'accuracy': r.get('accuracy'), 'current_incumbent_accuracy': r.get('current_incumbent_accuracy'), 'oracle_ceiling_on_package': r.get('oracle_ceiling_on_package'), 'recoverable_trace_terminal_cases': r.get('recoverable_trace_terminal_cases'), 'recoveries_among_gold_in_terminal_node_cases': r.get('recoveries_among_gold_in_terminal_node_cases'), 'failures_gold_present_in_terminal_nodes_not_chosen': r.get('failures_gold_present_in_terminal_nodes_not_chosen')
            })
    report = ['# Margin sweep report', '', f"- recommended_margin: {best['margin']}", '']
    for r in rows:
        report.append(f"## margin {r['margin']:.2f}")
        report.append(f"- overrides: {r['total_overrides']} fixes: {r['fixes']} breaks: {r['breaks']} net: {r['net_fixes_minus_breaks']} precision: {r['override_precision']:.3f} accuracy: {r['accuracy']:.3f}")
    (out / 'margin_sweep_report.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
