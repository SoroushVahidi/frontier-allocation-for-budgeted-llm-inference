#!/usr/bin/env python3
"""Build provider-agnostic multi-judge label requests for RelationReady seed data.

This script generates:
1. judge_requests.jsonl: requests for external judges (no manual labels or gold answers)
2. calibration_labels_private.jsonl: human labels for offline evaluation (optional)
3. request_build_report.md: report of what was generated

No API calls are made. This is for dry-run prompt generation and inspection only.
"""

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

RELATION_LABELS = {'ready', 'not_ready', 'uncertain', 'gold_inconsistent'}
ERROR_AXES = {
    'wrong_target_variable',
    'wrong_relation_composition',
    'wrong_process_state',
    'source_fact_missing',
    'unit_scale_error',
    'percentage_base_error',
    'per_unit_total_error',
    'total_difference_error',
    'original_final_state_error',
    'arithmetic_only_error',
    'formula_format_error',
    'prompt_gold_inconsistent',
    'insufficient_evidence',
}

EXPECTED_JSON_SCHEMA = {
    'type': 'object',
    'properties': {
        'relation_ready_label': {
            'type': 'string',
            'enum': list(RELATION_LABELS),
            'description': 'Whether the candidate trace correctly represents the semantic relation',
        },
        'first_error_axis': {
            'type': 'string',
            'enum': list(ERROR_AXES) + [''],
            'description': 'Primary error axis if not_ready; blank if ready',
        },
        'confidence': {
            'type': 'string',
            'enum': ['high', 'medium', 'low'],
            'description': 'Confidence in this label',
        },
        'rationale': {
            'type': 'string',
            'description': 'Short explanation for the label',
        },
    },
    'required': ['relation_ready_label', 'first_error_axis', 'confidence', 'rationale'],
}


_EMPTY_TARGET_PHRASE_FALLBACK = (
    'Not explicitly extracted. Use the question\'s requested quantity as the target.'
)


def build_prompt(row):
    """Build a prompt for a judge to label the row."""
    question = row.get('question', 'N/A')
    raw_phrase = row.get('target_phrase', '')
    target_phrase = raw_phrase.strip() if raw_phrase else ''
    if not target_phrase:
        target_phrase = _EMPTY_TARGET_PHRASE_FALLBACK
    candidate_answer = row.get('candidate_answer', 'N/A')
    candidate_trace = row.get('candidate_trace_short', 'N/A')

    prompt = f"""Please evaluate whether the following candidate trace and answer correctly represent the semantic relation requested by the question.

QUESTION:
{question}

TARGET PHRASE:
{target_phrase}

Note: The target phrase is an automatically extracted hint. If it is empty, vague, or type-like, use the quantity requested by the full question as the target.

CANDIDATE ANSWER:
{candidate_answer}

CANDIDATE TRACE:
{candidate_trace}

TASK:
Determine whether the candidate trace represents the correct semantic relation for computing the target phrase.

If the candidate trace is opaque, JSON-only, or lacks reasoning steps, judge only the visible trace and candidate answer. If the candidate appears wrong but the exact failure cannot be localized from the visible trace, use first_error_axis = insufficient_evidence. Do not infer hidden reasoning.

Respond with JSON containing:
- relation_ready_label: one of {{ready, not_ready, uncertain, gold_inconsistent}}
  - ready: the trace correctly computes the target relation
  - not_ready: the trace has semantic or arithmetic errors
  - uncertain: insufficient evidence to judge
  - gold_inconsistent: the trace is correct but conflicts with stated metadata
- first_error_axis: if not_ready, identify the primary error type from:
  - wrong_target_variable: identifies wrong variable or quantity
  - wrong_relation_composition: correct variables but wrong combination/formula
  - wrong_process_state: double-counts or misses state transitions
  - source_fact_missing: omits or misuses a source fact
  - unit_scale_error: wrong units or scaling
  - percentage_base_error: wrong percentage base
  - per_unit_total_error: confusion between per-unit and total
  - total_difference_error: asks for difference but computes something else
  - original_final_state_error: asks for initial but gives final state
  - arithmetic_only_error: correct relation, wrong computation
  - formula_format_error: malformed equation or notation
  - prompt_gold_inconsistent: conflicts with prompt statement
  - insufficient_evidence: cannot localize the error from visible trace
  Leave blank if ready
- confidence: high, medium, or low
- rationale: brief explanation"""

    return prompt


def check_prompt_for_leakage(prompt):
    """Check that prompt does not contain manual labels, gold answers, or label hints."""
    forbidden = [
        'relation_ready_label_manual',
        'first_error_axis_manual',
        'notes_manual',
        'gold_answer',
        'likely not_ready',
        'likely ready',
        'likely uncertain',
        'ready candidate',
        'not_ready candidate',
        'uncertain candidate',
        'good judge should label',
    ]
    for term in forbidden:
        if term in prompt:
            return False, f'Found forbidden term: {term}'
    return True, 'OK'


def build_requests(csv_path, max_rows=None, include_human_labels=False):
    """Build request JSONL from CSV."""
    requests = []
    calibration_labels = []
    skipped = []
    skipped_reasons = Counter()
    field_missing_counts = Counter()

    with csv_path.open('r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if max_rows and i >= max_rows:
                break

            row_id = row.get('row_id', f'row_{i}')

            # Check for required fields
            missing = []
            if not row.get('question'):
                missing.append('question')
                field_missing_counts['question'] += 1
            if not row.get('candidate_answer'):
                missing.append('candidate_answer')
                field_missing_counts['candidate_answer'] += 1
            if not row.get('candidate_trace_short'):
                missing.append('candidate_trace_short')
                field_missing_counts['candidate_trace_short'] += 1

            if missing:
                skipped.append(row_id)
                skipped_reasons[f'missing_{",".join(missing)}'] += 1
                continue

            # Build prompt
            prompt = build_prompt(row)
            prompt_ok, prompt_msg = check_prompt_for_leakage(prompt)
            if not prompt_ok:
                skipped.append(row_id)
                skipped_reasons[f'prompt_leakage: {prompt_msg}'] += 1
                continue

            # Build request object
            request_obj = {
                'row_id': row_id,
                'problem_id': row.get('problem_id', ''),
                'question': row.get('question', ''),
                'target_phrase': row.get('target_phrase', ''),
                'target_semantic_type': row.get('target_semantic_type', ''),
                'candidate_source': row.get('candidate_source', ''),
                'candidate_answer': row.get('candidate_answer', ''),
                'candidate_trace_short': row.get('candidate_trace_short', ''),
                'prompt': prompt,
                'expected_json_schema': EXPECTED_JSON_SCHEMA,
            }
            requests.append(request_obj)

            # Collect human labels for calibration (if requested)
            if include_human_labels:
                calibration_obj = {
                    'row_id': row_id,
                    'human_relation_ready_label': row.get('relation_ready_label_manual', ''),
                    'human_first_error_axis': row.get('first_error_axis_manual', ''),
                    'human_notes': row.get('notes_manual', ''),
                }
                calibration_labels.append(calibration_obj)

    return requests, calibration_labels, skipped, skipped_reasons, field_missing_counts


def generate_report(requests, calibration_labels, skipped, skipped_reasons, field_missing_counts):
    """Generate Markdown report."""
    lines = [
        '# RelationReady Multi-Judge Label Request Build Report',
        '',
        '## Summary',
        '',
        f'- **Emitted requests:** {len(requests)}',
        f'- **Skipped rows:** {len(skipped)}',
        f'- **Total input rows:** {len(requests) + len(skipped)}',
        '',
    ]

    if field_missing_counts:
        lines.append('## Missing Fields')
        lines.append('')
        for field, count in sorted(field_missing_counts.items()):
            lines.append(f'- `{field}`: {count} rows')
        lines.append('')

    if skipped_reasons:
        lines.append('## Skipped Rows')
        lines.append('')
        for reason, count in sorted(skipped_reasons.items()):
            lines.append(f'- {reason}: {count} rows')
        lines.append('')

    lines.append('## Safety Checks')
    lines.append('')
    lines.append('✓ All prompts checked for gold_answer leakage: OK')
    lines.append('✓ All prompts checked for manual_label leakage: OK')
    lines.append('✓ All prompts checked for notes leakage: OK')
    lines.append('')

    if calibration_labels:
        lines.append('## Calibration File')
        lines.append('')
        lines.append(
            f'- **File:** calibration_labels_private.jsonl'
        )
        lines.append(f'- **Rows:** {len(calibration_labels)}')
        lines.append('- **Contents:** Human labels for offline evaluation only (not sent to judges)')
        lines.append('')

    lines.append('## Expected Judge Response Schema')
    lines.append('')
    lines.append('```json')
    lines.append(json.dumps(EXPECTED_JSON_SCHEMA, indent=2))
    lines.append('```')
    lines.append('')

    lines.append('## Example Prompts')
    lines.append('')
    for i, req in enumerate(requests[:3], 1):
        lines.append(f'### Example {i}: {req["row_id"]}')
        lines.append('')
        lines.append('```')
        lines.append(req['prompt'])
        lines.append('```')
        lines.append('')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Build provider-agnostic multi-judge label requests for RelationReady seed data.'
    )
    parser.add_argument('--input-csv', required=True, help='Path to input CSV file')
    parser.add_argument('--output-dir', required=True, help='Path to output directory')
    parser.add_argument('--max-rows', type=int, default=None, help='Maximum rows to process')
    parser.add_argument(
        '--include-human-labels-in-eval-file',
        action='store_true',
        help='If set, create calibration_labels_private.jsonl with human labels',
    )
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f'Error: Input CSV not found: {input_path}', file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build requests
    requests, calibration_labels, skipped, skipped_reasons, field_missing_counts = build_requests(
        input_path,
        max_rows=args.max_rows,
        include_human_labels=args.include_human_labels_in_eval_file,
    )

    # Write judge_requests.jsonl
    judge_requests_path = output_dir / 'judge_requests.jsonl'
    with judge_requests_path.open('w', encoding='utf-8') as f:
        for req in requests:
            f.write(json.dumps(req) + '\n')

    # Write calibration_labels_private.jsonl if requested
    if calibration_labels:
        calibration_path = output_dir / 'calibration_labels_private.jsonl'
        with calibration_path.open('w', encoding='utf-8') as f:
            for label_obj in calibration_labels:
                f.write(json.dumps(label_obj) + '\n')

    # Generate and write report
    report = generate_report(requests, calibration_labels, skipped, skipped_reasons, field_missing_counts)
    report_path = output_dir / 'request_build_report.md'
    report_path.write_text(report, encoding='utf-8')

    # Print summary
    print(f'Request build complete: {input_path}')
    print(f'Output directory: {output_dir}')
    print()
    print(f'Emitted requests: {len(requests)}')
    print(f'Skipped rows: {len(skipped)}')
    if calibration_labels:
        print(f'Calibration labels: {len(calibration_labels)}')
    print()
    print(f'Files written:')
    print(f'  - {judge_requests_path.name}')
    if calibration_labels:
        print(f'  - calibration_labels_private.jsonl')
    print(f'  - request_build_report.md')
    print()
    print('✓ No APIs were called.')
    print('✓ All prompts are free of gold/manual label leakage.')


if __name__ == '__main__':
    main()
