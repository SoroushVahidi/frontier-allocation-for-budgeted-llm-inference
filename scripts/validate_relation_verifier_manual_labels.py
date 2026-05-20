#!/usr/bin/env python3
"""Validate and report on manually labeled RelationReady seed rows."""

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

ALLOWED_RELATION_LABELS = {'ready', 'not_ready', 'uncertain', 'gold_inconsistent'}
ALLOWED_ERROR_AXES = {
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


def validate_csv(csv_path):
    """Validate a manually labeled CSV and return findings."""
    findings = {
        'total_rows': 0,
        'labeled_rows': 0,
        'unlabeled_rows': 0,
        'invalid_relation_labels': [],
        'invalid_error_axes': [],
        'ready_with_axis': [],
        'not_ready_without_axis': [],
        'rows_by_label': defaultdict(list),
        'rows_by_axis': defaultdict(list),
        'rows_by_source': defaultdict(lambda: defaultdict(int)),
        'rows_by_split': defaultdict(lambda: defaultdict(int)),
        'uncertain_rows': [],
        'gold_inconsistent_rows': [],
        'all_rows': [],
    }

    with csv_path.open('r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            findings['all_rows'].append(row)
            findings['total_rows'] += 1

            relation_label = row.get('relation_ready_label_manual', '').strip()
            error_axis = row.get('first_error_axis_manual', '').strip()
            candidate_source = row.get('candidate_source', '').strip()
            split_group = row.get('split_group_id', '').strip()

            # Check if labeled
            if relation_label:
                findings['labeled_rows'] += 1
            else:
                findings['unlabeled_rows'] += 1

            # Validate relation label
            if relation_label and relation_label not in ALLOWED_RELATION_LABELS:
                findings['invalid_relation_labels'].append({
                    'row_id': row.get('row_id', 'UNKNOWN'),
                    'label': relation_label,
                })

            # Validate error axis
            if error_axis and error_axis not in ALLOWED_ERROR_AXES:
                findings['invalid_error_axes'].append({
                    'row_id': row.get('row_id', 'UNKNOWN'),
                    'axis': error_axis,
                })

            # Check ready rows with non-empty axis
            if relation_label == 'ready' and error_axis:
                findings['ready_with_axis'].append({
                    'row_id': row.get('row_id', 'UNKNOWN'),
                    'axis': error_axis,
                })

            # Check not_ready rows without axis
            if relation_label == 'not_ready' and not error_axis:
                findings['not_ready_without_axis'].append({
                    'row_id': row.get('row_id', 'UNKNOWN'),
                })

            # Track by label
            if relation_label:
                findings['rows_by_label'][relation_label].append(row)

            # Track by axis
            if error_axis:
                findings['rows_by_axis'][error_axis].append(row)

            # Track uncertain and gold_inconsistent
            if relation_label == 'uncertain':
                findings['uncertain_rows'].append(row)
            if relation_label == 'gold_inconsistent':
                findings['gold_inconsistent_rows'].append(row)

            # Track by source
            if candidate_source:
                findings['rows_by_source'][candidate_source][relation_label] += 1

            # Track by split
            if split_group:
                findings['rows_by_split'][split_group][relation_label] += 1

    return findings


def generate_report(findings):
    """Generate a Markdown report from validation findings."""
    lines = [
        '# RelationReady Manual Label Validation Report',
        '',
        '## Summary',
        '',
        f'- **Total rows:** {findings["total_rows"]}',
        f'- **Labeled rows:** {findings["labeled_rows"]}',
        f'- **Unlabeled rows:** {findings["unlabeled_rows"]}',
        '',
    ]

    # Issues
    issues = []
    if findings['invalid_relation_labels']:
        issues.append(
            f'**Invalid relation labels:** {len(findings["invalid_relation_labels"])}'
        )
    if findings['invalid_error_axes']:
        issues.append(
            f'**Invalid error axes:** {len(findings["invalid_error_axes"])}'
        )
    if findings['ready_with_axis']:
        issues.append(
            f'**Ready rows with non-empty axis:** {len(findings["ready_with_axis"])}'
        )
    if findings['not_ready_without_axis']:
        issues.append(
            f'**Not-ready rows with empty axis:** {len(findings["not_ready_without_axis"])}'
        )

    if issues:
        lines.append('## Issues Found')
        lines.append('')
        for issue in issues:
            lines.append(f'- {issue}')
        lines.append('')

        # Detail issues
        if findings['invalid_relation_labels']:
            lines.append('### Invalid Relation Labels')
            lines.append('')
            for item in findings['invalid_relation_labels']:
                lines.append(
                    f'- `{item["row_id"]}`: "{item["label"]}" '
                    f'(allowed: {", ".join(sorted(ALLOWED_RELATION_LABELS))})'
                )
            lines.append('')

        if findings['invalid_error_axes']:
            lines.append('### Invalid Error Axes')
            lines.append('')
            for item in findings['invalid_error_axes']:
                lines.append(
                    f'- `{item["row_id"]}`: "{item["axis"]}" '
                    f'(allowed: {", ".join(sorted(ALLOWED_ERROR_AXES))})'
                )
            lines.append('')

        if findings['ready_with_axis']:
            lines.append('### Ready Rows with Non-Empty Axis (should be blank)')
            lines.append('')
            for item in findings['ready_with_axis']:
                lines.append(f'- `{item["row_id"]}`: axis "{item["axis"]}" should be blank')
            lines.append('')

        if findings['not_ready_without_axis']:
            lines.append('### Not-Ready Rows with Empty Axis (should have value)')
            lines.append('')
            for item in findings['not_ready_without_axis']:
                lines.append(f'- `{item["row_id"]}`')
            lines.append('')
    else:
        lines.append('✓ **No validation issues found.**')
        lines.append('')

    # Label distribution
    lines.append('## Label Distribution')
    lines.append('')
    label_counts = Counter(k for k, v in findings['rows_by_label'].items() for _ in v)
    for label in sorted(ALLOWED_RELATION_LABELS):
        count = label_counts.get(label, 0)
        lines.append(f'- `{label}`: {count} rows')
    lines.append('')

    # Error axis distribution
    lines.append('## First Error Axis Distribution')
    lines.append('')
    axis_counts = Counter(k for k, v in findings['rows_by_axis'].items() for _ in v)
    for axis in sorted(ALLOWED_ERROR_AXES):
        count = axis_counts.get(axis, 0)
        if count > 0:
            lines.append(f'- `{axis}`: {count} rows')
    if not axis_counts:
        lines.append('(no error axes used)')
    lines.append('')

    # Candidate source distribution by label
    lines.append('## Candidate Source Distribution by Label')
    lines.append('')
    for source in sorted(findings['rows_by_source'].keys()):
        lines.append(f'### {source}')
        lines.append('')
        source_labels = findings['rows_by_source'][source]
        for label in sorted(source_labels.keys()):
            count = source_labels[label]
            lines.append(f'- `{label}`: {count}')
        lines.append('')

    # Split group distribution by label
    lines.append('## Split Group Distribution by Label')
    lines.append('')
    for split in sorted(findings['rows_by_split'].keys()):
        lines.append(f'### {split}')
        lines.append('')
        split_labels = findings['rows_by_split'][split]
        for label in sorted(split_labels.keys()):
            count = split_labels[label]
            lines.append(f'- `{label}`: {count}')
        lines.append('')

    # Example rows by label
    lines.append('## Example Rows by Label')
    lines.append('')
    for label in sorted(ALLOWED_RELATION_LABELS):
        if label in findings['rows_by_label']:
            rows = findings['rows_by_label'][label][:5]
            lines.append(f'### {label} (showing up to 5)')
            lines.append('')
            for i, row in enumerate(rows, 1):
                lines.append(f'#### Example {i}: {row.get("row_id", "UNKNOWN")}')
                lines.append('')
                lines.append(f'- **Question:** {row.get("question", "N/A")[:150]}...')
                lines.append(
                    f'- **Candidate Answer:** {row.get("candidate_answer", "N/A")}'
                )
                lines.append(f'- **Target Phrase:** {row.get("target_phrase", "N/A")}')
                lines.append(f'- **Candidate Source:** {row.get("candidate_source", "N/A")}')
                if row.get('first_error_axis_manual'):
                    lines.append(
                        f'- **First Error Axis:** {row.get("first_error_axis_manual", "N/A")}'
                    )
                lines.append(f'- **Notes:** {row.get("notes_manual", "N/A")[:200]}...')
                lines.append('')

    # All uncertain rows
    if findings['uncertain_rows']:
        lines.append('## All Uncertain Rows')
        lines.append('')
        for row in findings['uncertain_rows']:
            lines.append(f'### {row.get("row_id", "UNKNOWN")}')
            lines.append('')
            lines.append(f'- **Question:** {row.get("question", "N/A")}')
            lines.append(f'- **Candidate Answer:** {row.get("candidate_answer", "N/A")}')
            lines.append(f'- **Target Phrase:** {row.get("target_phrase", "N/A")}')
            lines.append(f'- **Target Semantic Type:** {row.get("target_semantic_type", "N/A")}')
            lines.append(f'- **Candidate Source:** {row.get("candidate_source", "N/A")}')
            lines.append(f'- **Notes:** {row.get("notes_manual", "N/A")}')
            lines.append('')

    # All gold_inconsistent rows
    if findings['gold_inconsistent_rows']:
        lines.append('## All Gold-Inconsistent Rows')
        lines.append('')
        for row in findings['gold_inconsistent_rows']:
            lines.append(f'### {row.get("row_id", "UNKNOWN")}')
            lines.append('')
            lines.append(f'- **Question:** {row.get("question", "N/A")}')
            lines.append(f'- **Candidate Answer:** {row.get("candidate_answer", "N/A")}')
            lines.append(f'- **Target Phrase:** {row.get("target_phrase", "N/A")}')
            lines.append(f'- **Candidate Source:** {row.get("candidate_source", "N/A")}')
            lines.append(f'- **Notes:** {row.get("notes_manual", "N/A")}')
            lines.append('')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Validate and report on manually labeled RelationReady seed rows.'
    )
    parser.add_argument('--input-csv', required=True, help='Path to input CSV file')
    parser.add_argument('--output-md', required=True, help='Path to output Markdown report')
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_md)

    if not input_path.exists():
        print(f'Error: Input CSV not found: {input_path}', file=sys.stderr)
        sys.exit(1)

    # Validate and generate findings
    findings = validate_csv(input_path)

    # Generate report
    report = generate_report(findings)

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding='utf-8')

    # Print summary to stdout
    has_issues = (
        findings['invalid_relation_labels']
        or findings['invalid_error_axes']
        or findings['ready_with_axis']
        or findings['not_ready_without_axis']
    )

    print(f'Validation complete: {input_path}')
    print(f'Report written to: {output_path}')
    print()
    print(f'Total rows: {findings["total_rows"]}')
    print(f'Labeled rows: {findings["labeled_rows"]}')
    print(f'Unlabeled rows: {findings["unlabeled_rows"]}')
    print()

    if has_issues:
        print('⚠ Issues found:')
        if findings['invalid_relation_labels']:
            print(f'  - Invalid relation labels: {len(findings["invalid_relation_labels"])}')
        if findings['invalid_error_axes']:
            print(f'  - Invalid error axes: {len(findings["invalid_error_axes"])}')
        if findings['ready_with_axis']:
            print(f'  - Ready rows with axis: {len(findings["ready_with_axis"])}')
        if findings['not_ready_without_axis']:
            print(f'  - Not-ready rows without axis: {len(findings["not_ready_without_axis"])}')
        sys.exit(1)
    else:
        print('✓ All labels are valid.')
        sys.exit(0)


if __name__ == '__main__':
    main()
