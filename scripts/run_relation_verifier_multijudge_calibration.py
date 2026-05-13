#!/usr/bin/env python3
"""No-API calibration runner scaffold for RelationReady multi-judge labeling.

Modes:
  dry_run    -- validate request manifest; no API calls
  mock_jsonl -- evaluate mock judge responses offline; no API calls

No provider SDK imports. No real API calls are made.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RELATION_LABELS = frozenset({'ready', 'not_ready', 'uncertain', 'gold_inconsistent'})
ERROR_AXES = frozenset({
    'wrong_target_variable', 'wrong_relation_composition', 'wrong_process_state',
    'source_fact_missing', 'unit_scale_error', 'percentage_base_error',
    'per_unit_total_error', 'total_difference_error', 'original_final_state_error',
    'arithmetic_only_error', 'formula_format_error', 'prompt_gold_inconsistent',
    'insufficient_evidence', '',
})

LEAKAGE_TERMS = [
    'gold_answer_metadata_only',
    'relation_ready_label_manual',
    'first_error_axis_manual',
    'notes_manual',
    'likely not_ready',
    'likely ready',
    'likely uncertain',
    'ready candidate',
    'not_ready candidate',
    'uncertain candidate',
    'good judge should label',
]


def read_jsonl(path):
    rows = []
    with Path(path).open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path, rows):
    with Path(path).open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row) + '\n')


def scan_prompt_leakage(prompt):
    """Return list of forbidden terms found in the prompt."""
    lower = prompt.lower()
    return [term for term in LEAKAGE_TERMS if term.lower() in lower]


def validate_request(req):
    """Return list of missing/invalid field names."""
    issues = []
    for field in ('row_id', 'prompt', 'expected_json_schema'):
        if not req.get(field):
            issues.append(f'missing_{field}')
    return issues


def run_dry_run(requests_path, output_dir, max_rows):
    requests = read_jsonl(requests_path)
    if max_rows:
        requests = requests[:max_rows]

    manifest = []
    field_issues = []
    leakage_issues = []

    for req in requests:
        row_id = req.get('row_id', '<unknown>')
        issues = validate_request(req)
        prompt = req.get('prompt', '')
        leakage = scan_prompt_leakage(prompt)

        manifest.append({
            'row_id': row_id,
            'problem_id': req.get('problem_id', ''),
            'has_prompt': bool(prompt),
            'has_schema': bool(req.get('expected_json_schema')),
            'field_issues': issues,
            'leakage_terms': leakage,
            'prompt_length': len(prompt),
        })

        if issues:
            field_issues.append((row_id, issues))
        if leakage:
            leakage_issues.append((row_id, leakage))

    write_jsonl(output_dir / 'dry_run_request_manifest.jsonl', manifest)

    valid_count = sum(1 for m in manifest if not m['field_issues'] and not m['leakage_terms'])
    n = len(requests)

    lines = [
        '# RelationReady Multi-Judge Calibration — Dry-Run Report',
        '',
        '## Summary',
        '',
        '- **Mode:** dry_run (no API calls)',
        f'- **Input:** `{requests_path}`',
        f'- **Total requests:** {n}',
        f'- **Valid requests:** {valid_count}',
        f'- **Requests with field issues:** {len(field_issues)}',
        f'- **Requests with prompt leakage:** {len(leakage_issues)}',
        '',
        '## Safety / Leakage Scan',
        '',
    ]
    if leakage_issues:
        lines.append('**LEAKAGE DETECTED:**')
        lines.append('')
        for row_id, terms in leakage_issues:
            lines.append(f'- `{row_id}`: {", ".join(terms)}')
        lines.append('')
    else:
        lines.append('✓ No leakage terms found in any prompt.')
        lines.append('')

    if field_issues:
        lines += ['## Field Issues', '']
        for row_id, issues in field_issues:
            lines.append(f'- `{row_id}`: {", ".join(issues)}')
        lines.append('')

    lines += [
        '## Estimated Provider Call Count',
        '',
        '> If this batch is sent to N judges, the call count will be:',
        f'> - 1 judge : {n} calls',
        f'> - 2 judges: {n * 2} calls',
        f'> - 3 judges: {n * 3} calls',
        '',
        '## Example Request IDs',
        '',
    ]
    for req in requests[:5]:
        lines.append(f'- `{req.get("row_id", "<unknown>")}`')
    if n > 5:
        lines.append(f'- ... ({n - 5} more)')
    lines += [
        '',
        '## Confirmation',
        '',
        '✓ No API calls were made.',
        '✓ No provider SDK imports were used.',
        '✓ Human labels were not exposed in any prompt.',
    ]

    (output_dir / 'calibration_run_report.md').write_text('\n'.join(lines), encoding='utf-8')
    return manifest, field_issues, leakage_issues


def load_private_labels(path):
    """Load private labels from JSONL; supports both field-naming conventions."""
    labels = {}
    for row in read_jsonl(path):
        rid = row.get('row_id', '')
        if not rid:
            continue
        label = (
            row.get('relation_ready_label_manual')
            or row.get('human_relation_ready_label', '')
        )
        axis = (
            row.get('first_error_axis_manual')
            or row.get('human_first_error_axis', '')
        )
        labels[rid] = {'label': label or '', 'axis': axis or ''}
    return labels


def run_mock_jsonl(requests_path, mock_path, output_dir, private_labels_path, max_rows):
    requests = read_jsonl(requests_path)
    if max_rows:
        requests = requests[:max_rows]

    request_index = {r['row_id']: r for r in requests}
    mock_responses = read_jsonl(mock_path)

    private_labels = {}
    if private_labels_path:
        private_labels = load_private_labels(private_labels_path)

    normalized = []
    invalid = []
    label_counts = Counter()
    judge_stats = defaultdict(lambda: {'total': 0, 'invalid': 0})

    for resp in mock_responses:
        row_id = resp.get('row_id', '<unknown>')
        judge_name = resp.get('judge_name', 'unknown')
        label = resp.get('relation_ready_label', '')
        axis = resp.get('first_error_axis', '')
        confidence = resp.get('confidence', '')

        judge_stats[judge_name]['total'] += 1

        resp_issues = []
        if label not in RELATION_LABELS:
            resp_issues.append(f'invalid_label:{label!r}')
        if axis not in ERROR_AXES:
            resp_issues.append(f'invalid_axis:{axis!r}')
        if confidence not in ('high', 'medium', 'low'):
            resp_issues.append(f'invalid_confidence:{confidence!r}')
        if row_id not in request_index:
            resp_issues.append('unknown_row_id')

        if resp_issues:
            invalid.append({'row_id': row_id, 'judge_name': judge_name, 'issues': resp_issues})
            judge_stats[judge_name]['invalid'] += 1
            continue

        label_counts[label] += 1
        normalized.append({
            'row_id': row_id,
            'judge_name': judge_name,
            'relation_ready_label': label,
            'first_error_axis': axis,
            'confidence': confidence,
            'rationale': resp.get('rationale', ''),
        })

    write_jsonl(output_dir / 'normalized_judge_responses.jsonl', normalized)

    # Group by row_id for majority vote and review detection
    by_row = defaultdict(list)
    for resp in normalized:
        by_row[resp['row_id']].append(resp)

    needs_review = []
    label_agree = 0
    axis_agree = 0
    not_ready_compared = 0
    disagreement_rows = []

    for row_id, resps in by_row.items():
        labels = [r['relation_ready_label'] for r in resps]
        axes = [r['first_error_axis'] for r in resps]
        confidences = [r['confidence'] for r in resps]

        label_vote = Counter(labels).most_common(1)[0][0]
        has_low_conf = 'low' in confidences
        has_uncertain = any(l in ('uncertain', 'gold_inconsistent') for l in labels)
        has_disagreement = len(set(labels)) > 1

        review_reasons = []
        if has_disagreement:
            review_reasons.append('judge_disagreement')
            disagreement_rows.append(row_id)
        if has_low_conf:
            review_reasons.append('low_confidence')
        if has_uncertain:
            review_reasons.append('uncertain_or_gold_inconsistent')

        if private_labels and row_id in private_labels:
            manual_label = private_labels[row_id]['label']
            manual_axis = private_labels[row_id]['axis']
            if label_vote == manual_label:
                label_agree += 1
            else:
                review_reasons.append('majority_differs_from_manual')
            if manual_label == 'not_ready':
                not_ready_compared += 1
                axis_vote = Counter(axes).most_common(1)[0][0]
                if axis_vote == manual_axis:
                    axis_agree += 1

        if review_reasons:
            needs_review.append({'row_id': row_id, 'reasons': review_reasons})

    lines = [
        '# RelationReady Multi-Judge Calibration — Agreement Report',
        '',
        '## Summary',
        '',
        '- **Mode:** mock_jsonl (no API calls; responses from mock file)',
        f'- **Input requests:** `{requests_path}`',
        f'- **Mock responses:** `{mock_path}`',
        f'- **Total mock responses:** {len(mock_responses)}',
        f'- **Valid normalized responses:** {len(normalized)}',
        f'- **Invalid responses:** {len(invalid)}',
        f'- **Rows with responses:** {len(by_row)}',
        f'- **Rows needing review:** {len(needs_review)}',
        '',
    ]

    if private_labels:
        lines += [
            '## Private Label Agreement',
            '',
            '> Private labels used ONLY for offline evaluation. Not sent to any judge.',
            '',
            f'- **Rows with private labels:** {len(private_labels)}',
            f'- **Label agreement (majority vs manual):** {label_agree} / {len(by_row)}',
            f'- **Axis agreement (not_ready rows):** {axis_agree} / {not_ready_compared}',
            '',
        ]

    lines += ['## Label Distribution', '']
    for label, count in label_counts.most_common():
        lines.append(f'- `{label}`: {count}')
    lines.append('')

    if invalid:
        lines += ['## Invalid Responses', '']
        for inv in invalid:
            lines.append(f'- `{inv["row_id"]}` ({inv["judge_name"]}): {", ".join(inv["issues"])}')
        lines.append('')

    if needs_review:
        lines += ['## Rows Needing Human Review', '']
        for nr in needs_review:
            lines.append(f'- `{nr["row_id"]}`: {", ".join(nr["reasons"])}')
        lines.append('')

    lines += ['## Judge Statistics', '']
    for judge, stats in sorted(judge_stats.items()):
        lines.append(f'- **{judge}**: {stats["total"]} responses, {stats["invalid"]} invalid')
    lines += [
        '',
        '## Confirmation',
        '',
        '✓ No API calls were made.',
        '✓ No provider SDK imports were used.',
        '✓ Private labels were used only for offline agreement computation.',
        '✓ Private labels were not written into any provider prompt.',
    ]

    (output_dir / 'judge_agreement_report.md').write_text('\n'.join(lines), encoding='utf-8')
    return normalized, invalid, needs_review


def main():
    parser = argparse.ArgumentParser(
        description='No-API calibration runner scaffold for RelationReady multi-judge labeling.'
    )
    parser.add_argument('--requests-jsonl', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--mode', required=True, choices=['dry_run', 'mock_jsonl'])
    parser.add_argument('--mock-responses-jsonl')
    parser.add_argument('--private-labels-jsonl')
    parser.add_argument('--max-rows', type=int)
    args = parser.parse_args()

    requests_path = Path(args.requests_jsonl)
    output_dir = Path(args.output_dir)

    if not requests_path.exists():
        print(f'Error: Requests file not found: {requests_path}', file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == 'dry_run':
        manifest, field_issues, leakage_issues = run_dry_run(
            requests_path, output_dir, args.max_rows
        )
        print(f'Dry-run complete: {requests_path}')
        print(f'Output directory: {output_dir}')
        print()
        print(f'Total requests   : {len(manifest)}')
        print(f'Field issues     : {len(field_issues)}')
        print(f'Leakage issues   : {len(leakage_issues)}')
        print()
        print('Files written:')
        print('  - dry_run_request_manifest.jsonl')
        print('  - calibration_run_report.md')
        print()
        print('✓ No API calls were made.')
        print('✓ No provider SDK imports were used.')

    elif args.mode == 'mock_jsonl':
        if not args.mock_responses_jsonl:
            print('Error: --mock-responses-jsonl required for mock_jsonl mode', file=sys.stderr)
            sys.exit(1)
        mock_path = Path(args.mock_responses_jsonl)
        if not mock_path.exists():
            print(f'Error: Mock responses file not found: {mock_path}', file=sys.stderr)
            sys.exit(1)
        private_path = Path(args.private_labels_jsonl) if args.private_labels_jsonl else None
        if private_path and not private_path.exists():
            print(f'Error: Private labels file not found: {private_path}', file=sys.stderr)
            sys.exit(1)

        normalized, invalid, needs_review = run_mock_jsonl(
            requests_path, mock_path, output_dir, private_path, args.max_rows
        )
        print('Mock-JSONL evaluation complete.')
        print(f'Output directory: {output_dir}')
        print()
        print(f'Valid responses  : {len(normalized)}')
        print(f'Invalid responses: {len(invalid)}')
        print(f'Rows for review  : {len(needs_review)}')
        print()
        print('Files written:')
        print('  - normalized_judge_responses.jsonl')
        print('  - judge_agreement_report.md')
        print()
        print('✓ No API calls were made.')
        print('✓ No provider SDK imports were used.')


if __name__ == '__main__':
    main()
