#!/usr/bin/env python3
"""Azure OpenAI assisted labeler for RelationReady candidate rows.

Modes
-----
dry_run   -- validate rows and build prompt requests; no network calls
api       -- submit real Azure OpenAI requests (requires --allow-api)

Reads an input CSV produced by export_relation_verifier_positive_candidate_batch.py
and labels unlabeled rows using the configured Azure OpenAI deployment.

No openai SDK imported at module level.  No API calls unless --allow-api is set.
Gold metadata (is_correct_offline_metadata) and manual labels/notes are
never included in prompts.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RELATION_LABELS = frozenset({'ready', 'not_ready', 'uncertain', 'gold_inconsistent'})
ERROR_AXES = frozenset({
    'source_fact_missing', 'unit_scale_error', 'process_state_error',
    'relation_type_error', 'arithmetic_error', 'other', '',
})
CONFIDENCE_VALUES = frozenset({'high', 'medium', 'low'})

# Fields that must never appear in a prompt (gold / label leakage)
_EXCLUDED_FIELDS = frozenset({
    'is_correct_offline_metadata',
    'relation_ready_label_manual',
    'first_error_axis_manual',
    'notes_manual',
})

# Leakage detector terms (lower-cased at check time)
_LEAKAGE_TERMS = [
    'gold_answer_metadata_only',
    'is_correct_offline_metadata',
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

# Prompt-allowed fields (explicitly whitelisted)
_PROMPT_FIELDS = [
    'row_id',
    'question',
    'candidate_answer',
    'candidate_trace_short',
    'trace_quality_flags',
    'candidate_source',
]

_RUBRIC = """\
Annotation rubric:

WHAT "ready" MEANS — RELATION STRUCTURE, NOT ARITHMETIC CORRECTNESS:
- "ready" means the visible trace uses the correct variables, source facts, units,
  and operations to establish the target computational relation, regardless of whether
  a single arithmetic calculation is slightly wrong.
- A minor arithmetic slip (e.g. 5*7=35 when it should be 5*7=35, or rounding error)
  does NOT make a row not_ready if the correct relation pathway is fully established.
- A PAL/code trace that defines variables and the correct final expression
  (e.g. `answer = a + b`) establishes the relation even if the evaluated numeric
  value is not shown inline.
- Do NOT flag arithmetic_error merely because the candidate answer seems numerically
  off — only flag it when the arithmetic mistake structurally prevents the trace from
  establishing the candidate answer.

DO NOT SECOND-GUESS THE TRACE'S ARITHMETIC:
- Your task is to judge whether the visible relation structure is correct, NOT to
  independently solve the problem and compare against your own answer.
- If the trace uses the correct quantities and the correct operator for the target
  relation, mark ready — even if you would write the expression in a different order.
- EQUIVALENT FORMULAS MUST BE ACCEPTED: expressions that are algebraically equivalent
  to the correct formula are correct. For example:
    `250 / 300 * 5`,  `250 * 5 / 300`,  and  `(250 * 5) / 300`
  all express "total_calories / grams_per_bag * servings" and yield the same value.
  Do NOT flag operator ordering as unit_scale_error or arithmetic_error when the
  expression is algebraically equivalent and uses the correct source quantities.
- CONVERSION FACTORS: multiplying a $20-bill count by 4 to obtain the equivalent
  $5-bill count IS CORRECT (each $20 = four $5 bills). Do not flag as arithmetic_error
  because you expected division. Always ask: does this operator correctly represent the
  target relation, not just: does it match what I would write?
- IMPLICIT INTERMEDIATE STEPS: If the trace's stated intermediate value is consistent
  with the question's source facts, treat it as established even if the sub-derivation
  is not spelled out. For example, if the trace writes "8 pounds of chihuahua stuffing"
  and the question states 4 chihuahua beds × 2 lbs each, the value 8 is consistent —
  do NOT flag source_fact_missing merely because "4 × 2 = 8" was not written explicitly.
- SELF-CONTRADICTION CHECK: Before returning arithmetic_error or unit_scale_error,
  verify your rationale is internally consistent. If your reasoning acknowledges that a
  trace value equals the correct quantity (e.g., "the trace states 5 pounds, and
  average(8, 2) = 5"), you MUST NOT simultaneously call that value wrong. A value
  cannot be both correct by your own calculation and an error. If you catch yourself
  writing this, discard the error and reconsider whether the trace is actually ready.
- Only flag arithmetic_error when the operator is fundamentally wrong in a way that
  cannot be reconciled: e.g., division where the relation requires multiplication for
  a rate×time computation, or subtraction where addition is structurally required.

TRUNCATION RULE:
- Do NOT mark source_fact_missing when only a trivial final aggregation
  (a sum or subtraction of two already-computed visible values) is absent, and the
  candidate answer matches that obvious aggregation.
- TRIVIAL means: every component of the final step is explicitly computed and visible
  in the trace, and the only missing step is combining them with a basic operation
  (sum, difference, or product of already-stated values). Examples:
    • Addition:    trace shows 1650 and 800, answer = 2450 → `1650 + 800` is trivial.
    • Subtraction: trace shows $30 (total money) and $24 (cost), answer = 6
                   → `$30 - $24` is trivial even if the trace truncates after "has $30 -".
    • Combination: trace states 8 lbs (chihuahua total) and 15 lbs (collie total),
                   answer = 23 → `8 + 15` is trivial.
  In all these cases mark ready (is_hesitant=true if truncation is visible).
- NOT TRIVIAL means: the final step requires applying a rate, multiplying by a count,
  or using a source fact that does not appear anywhere in the visible trace.
- Mark not_ready/source_fact_missing ONLY when an essential relation step, source
  fact, unit conversion, or nontrivial intermediate computation is missing.
- If truncation hides a crucial step that is genuinely needed to establish the answer,
  mark not_ready.

HESITATION RULE — you must flag is_hesitant=true in these situations:
- Deciding between ready and not_ready because of truncation ambiguity.
- Deciding between ready and arithmetic_error because of a small arithmetic slip.
- Deciding between source_fact_missing and ready due to an implicit final aggregation.
- About to mark not_ready because a formula is differently ordered — first check
  whether it is algebraically equivalent to the correct formula.
- About to mark arithmetic_error or unit_scale_error for a conversion factor —
  first verify whether the operator (× vs ÷) is structurally correct for the relation.
- All required component values are explicitly computed and visible; only the final
  aggregation line is absent or truncated.
- Uncertain which axis applies.
- Any case where a careful annotator would pause before deciding.
Do NOT report high confidence on every row — boundary cases exist in this dataset.

LABEL DEFINITIONS:
- "ready": trace visibly establishes the correct relation/computational pathway.
  There must be visible reasoning steps — a final-answer-only or opaque trace is
  not sufficient.
- "not_ready": trace fails to establish the relation.  Mark the first_error_axis.
- "uncertain": genuinely ambiguous; valid arguments exist for both ready and not_ready.
- "gold_inconsistent": trace/answer contradicts the gold answer in a way that makes
  the relation status indeterminate.

first_error_axis values (use "" for ready/uncertain/gold_inconsistent):
  source_fact_missing   -- essential intermediate computation absent from trace
  unit_scale_error      -- wrong unit, wrong scale, wrong denominator, wrong rate base
  process_state_error   -- wrong state/time-point in a multi-step process
  relation_type_error   -- wrong relation type (rate vs total, ratio vs difference, etc.)
  arithmetic_error      -- arithmetic mistake that structurally prevents establishing
                           the candidate answer (not a minor slip in an otherwise correct trace)
  other                 -- error present but doesn't fit above axes
  ""                    -- no error (use for ready / uncertain / gold_inconsistent)"""

_JSON_SCHEMA_EXAMPLE = """\
{
  "row_id": "<same as input>",
  "relation_ready_label": "ready|not_ready|uncertain|gold_inconsistent",
  "first_error_axis": "source_fact_missing|unit_scale_error|process_state_error|relation_type_error|arithmetic_error|other|",
  "confidence": "high|medium|low",
  "is_hesitant": true,
  "hesitation_reason": "brief reason or empty string",
  "rationale": "one or two sentence explanation"
}"""

_FEW_SHOT_EXAMPLES = """\
=== FEW-SHOT EXAMPLES (synthetic, illustrate the rubric) ===

--- EXAMPLE 1: ready — trivial final aggregation omitted but relation is established ---
question: Alice earns $40 on Monday and $35 on Tuesday. How much total?
candidate_answer: 75
candidate_trace: monday = 40
tuesday = 35
answer = monday + tuesday
print(answer)
→ Label: ready  axis: ""  confidence: high  is_hesitant: false
Reason: The trace defines both source values and the correct summation relation.
The numeric result is not shown inline but the expression `monday + tuesday`
fully establishes the total-earnings relation. Trivial aggregation omission does
not prevent ready.

--- EXAMPLE 2: ready — minor arithmetic slip, correct relation structure ---
question: A bag has 8 red and 5 blue balls. How many total?
candidate_answer: 14
candidate_trace: total = 8 + 5 = 14
→ Label: ready  axis: ""  confidence: medium  is_hesitant: true
hesitation_reason: arithmetic slip (8+5=13, not 14) but relation structure correct
Reason: The trace uses the correct addition relation over the correct operands.
The arithmetic slip is minor and does not change the relation structure. Label ready
per the convention; flag is_hesitant because of the arithmetic discrepancy.

--- EXAMPLE 3: not_ready — essential computation entirely absent ---
question: A worker earns $12/hr and works 8 hrs on Monday and 6 hrs on Tuesday.
What is the total pay?
candidate_answer: 168
candidate_trace: Monday hours = 8. Tuesday hours = 6.
→ Label: not_ready  axis: source_fact_missing  confidence: high  is_hesitant: false
Reason: The trace never multiplies hours by the wage rate ($12/hr) for either day,
so the pay relation is never established. Essential intermediate computations are
fully absent.

--- EXAMPLE 4: not_ready — wrong relation type (rate confused with total) ---
question: A car travels 60 km/h for 3 hours. How far did it travel?
candidate_answer: 20
candidate_trace: distance = 60 / 3 = 20
→ Label: not_ready  axis: relation_type_error  confidence: high  is_hesitant: false
Reason: The trace divides speed by time instead of multiplying, using the wrong
relation operator for distance = rate × time. This is a structural relation error,
not a minor arithmetic slip.

--- EXAMPLE 5: ready — correct conversion factor, do not second-guess ---
question: Thomas has 15 twenty-dollar bills and exchanges them all for five-dollar bills.
How many five-dollar bills does he receive?
candidate_answer: 60
candidate_trace: five_dollar_bills = twenty_dollar_bills * 4
→ Label: ready  axis: ""  confidence: high  is_hesitant: false
Reason: Each $20 bill equals four $5 bills, so multiplying by 4 IS the correct
conversion relation. Do NOT flag as arithmetic_error. The judge must not substitute
their own independent calculation (÷4 would be wrong here).

--- EXAMPLE 6: ready — algebraically equivalent formula, do not flag as unit error ---
question: A bag has 5 servings of 250 calories each and weighs 300g. Calories per gram?
candidate_answer: 4.17
candidate_trace: cal_per_gram = 250 / 300 * 5
→ Label: ready  axis: ""  confidence: high  is_hesitant: false
Reason: `250 / 300 * 5` equals `(250 * 5) / 300` by left-to-right evaluation —
algebraically equivalent. The formula uses the correct source quantities and the
correct relation. Do NOT flag as unit_scale_error because multiplication and division
are reordered; the result and the relation are identical.

--- EXAMPLE 7: ready — trivial final sum truncated, all components visible ---
question: A dancer taps for 3 minutes at 550/min and 2 minutes at 400/min. Total taps?
candidate_answer: 2450
candidate_trace: arm_down_taps = 550 * 3 = 1650
arm_raised_taps = 400 * 2 = 800
[trace truncated]
→ Label: ready  axis: ""  confidence: medium  is_hesitant: true
hesitation_reason: final sum 1650+800 not written but both components are visible
Reason: Both components (1650 and 800) are explicitly computed and visible.
Candidate answer 2450 = 1650 + 800 exactly. The final summation line is trivial —
apply the trivial-aggregation rule and mark ready. Flag is_hesitant for the truncation.

--- EXAMPLE 8: ready — trivial final subtraction truncated (monetary change) ---
question: Michael has $30. He spends $24 on hay. How much change does he have?
candidate_answer: 6
candidate_trace: hay_cost = 8 * 3 = 24. Michael has 6 * 5 = 30 dollars.
After buying the hay for $24, he has $30 -
[trace truncated mid-subtraction]
→ Label: ready  axis: ""  confidence: medium  is_hesitant: true
hesitation_reason: subtraction $30 - $24 not completed but both operands are visible
Reason: Both operands ($30 total money and $24 cost) are explicitly computed and
visible. Candidate answer 6 = 30 - 24 exactly. The final subtraction is trivial —
this is the same pattern as the 1650 + 800 = 2450 case. Apply the trivial-aggregation
rule and mark ready even though the trace truncates mid-operation.

=== END OF EXAMPLES ==="""


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def read_csv_rows(path):
    with Path(path).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_jsonl(path, rows):
    with Path(path).open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def append_jsonl(path, row):
    with Path(path).open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


def read_jsonl(path):
    rows = []
    p = Path(path)
    if not p.exists():
        return rows
    with p.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Leakage / validation
# ---------------------------------------------------------------------------

def scan_leakage(text):
    lower = text.lower()
    return [term for term in _LEAKAGE_TERMS if term.lower() in lower]


def validate_prompt_text(prompt_text):
    """Return list of leakage terms found; empty list is clean."""
    return scan_leakage(prompt_text)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(row):
    """Build the Azure prompt for a single CSV row.

    Only uses _PROMPT_FIELDS.  Excluded fields are never touched.
    Returns the prompt string.
    """
    parts = [
        "You are a precise annotation judge for a math-reasoning dataset.",
        "",
        "Evaluate whether the candidate trace and answer correctly establish the "
        "semantic relation requested by the question.",
        "",
        _RUBRIC,
        "",
        _FEW_SHOT_EXAMPLES,
        "",
        "=== INPUT ROW ===",
        f"row_id: {row.get('row_id', '')}",
        f"question: {row.get('question', '')}",
        f"candidate_answer: {row.get('candidate_answer', '')}",
        "",
        "candidate_trace:",
        row.get('candidate_trace_short', '').strip(),
        "",
        f"trace_quality_flags: {row.get('trace_quality_flags', '')}",
        f"candidate_source: {row.get('candidate_source', '')}",
        "",
        "=== TASK ===",
        "Respond with ONLY a JSON object matching this exact schema:",
        _JSON_SCHEMA_EXAMPLE,
        "",
        "Do not include any text outside the JSON object.",
    ]
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Row selection
# ---------------------------------------------------------------------------

def select_rows(all_rows, start_index, max_rows, row_ids_set, include_labeled):
    """Return the selected subset of rows.

    Priority: if row_ids_set is non-empty it takes precedence over start_index.
    """
    if row_ids_set:
        selected = [r for r in all_rows if r.get('row_id', '') in row_ids_set]
    else:
        selected = all_rows[start_index:]
        if max_rows is not None:
            selected = selected[:max_rows]

    if not include_labeled:
        selected = [r for r in selected if not r.get('relation_ready_label_manual', '').strip()]

    return selected


# ---------------------------------------------------------------------------
# Response normalization
# ---------------------------------------------------------------------------

def normalize_response(row_id, deployment, response_text, raw_finish_reason):
    """Parse and validate an Azure response.

    Returns (normalized_dict, error_string).  error_string is None on success.
    """
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        # Try extracting JSON from surrounding text
        import re
        m = re.search(r'\{.*\}', response_text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group())
            except json.JSONDecodeError:
                return None, f'json_parse_error:{exc}'
        else:
            return None, f'json_parse_error:{exc}'

    label = parsed.get('relation_ready_label', '')
    axis = parsed.get('first_error_axis', '')
    confidence = parsed.get('confidence', '')
    is_hesitant = bool(parsed.get('is_hesitant', False))
    hesitation_reason = str(parsed.get('hesitation_reason', ''))
    rationale = str(parsed.get('rationale', ''))
    returned_row_id = str(parsed.get('row_id', ''))

    issues = []
    if label not in RELATION_LABELS:
        issues.append(f'invalid_label:{label!r}')
    if axis not in ERROR_AXES:
        issues.append(f'invalid_axis:{axis!r}')
    if confidence not in CONFIDENCE_VALUES:
        issues.append(f'invalid_confidence:{confidence!r}')
    if returned_row_id and returned_row_id != row_id:
        issues.append(f'row_id_mismatch:expected={row_id!r} got={returned_row_id!r}')

    if issues:
        return None, f'validation_errors:{";".join(issues)}'

    normalized = {
        'row_id': row_id,
        'judge_name': f'azure:{deployment}',
        'relation_ready_label': label,
        'first_error_axis': axis,
        'confidence': confidence,
        'is_hesitant': is_hesitant,
        'hesitation_reason': hesitation_reason,
        'rationale': rationale,
        'finish_reason': raw_finish_reason,
    }
    return normalized, None


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------

def run_dry_run(args, all_rows, output_dir):
    selected = select_rows(
        all_rows,
        start_index=args.start_index,
        max_rows=args.max_rows,
        row_ids_set=set(args.row_ids.split(',')) if args.row_ids else set(),
        include_labeled=args.include_labeled,
    )

    requests = []
    leakage_count = 0
    labeled_skipped = sum(
        1 for r in (all_rows[args.start_index:] if not args.row_ids else
                    [r for r in all_rows if r.get('row_id', '') in
                     set(args.row_ids.split(','))])
        if r.get('relation_ready_label_manual', '').strip()
    ) if not args.include_labeled else 0

    for row in selected:
        prompt = build_prompt(row)
        leakage = validate_prompt_text(prompt)
        if leakage:
            leakage_count += 1

        req = {
            'row_id': row.get('row_id', ''),
            'prompt_length': len(prompt),
            'leakage_terms': leakage,
            'has_question': bool(row.get('question', '').strip()),
            'has_trace': bool(row.get('candidate_trace_short', '').strip()),
        }
        requests.append(req)

    # Write requests JSONL
    req_rows = []
    for row in selected:
        prompt = build_prompt(row)
        req_rows.append({
            'row_id': row.get('row_id', ''),
            'deployment': args.deployment or os.environ.get('AZURE_OPENAI_DEPLOYMENT', ''),
            'prompt': prompt,
            'temperature': args.temperature,
            'max_completion_tokens': 256,
        })
    write_jsonl(output_dir / 'azure_label_requests.jsonl', req_rows)

    # Manifest
    manifest = {
        'mode': 'dry_run',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'input_csv': str(args.input_csv),
        'total_rows_in_csv': len(all_rows),
        'start_index': args.start_index,
        'max_rows': args.max_rows,
        'row_ids_filter': args.row_ids or None,
        'include_labeled': args.include_labeled,
        'rows_selected': len(selected),
        'rows_with_leakage': leakage_count,
        'labeled_rows_skipped': labeled_skipped,
        'deployment': args.deployment or os.environ.get('AZURE_OPENAI_DEPLOYMENT', ''),
        'api_calls_made': 0,
        'gold_metadata_excluded': True,
        'manual_labels_excluded': True,
    }
    with (output_dir / 'run_manifest.json').open('w') as f:
        json.dump(manifest, f, indent=2)

    # Summary report
    lines = [
        '# Azure RelationReady Labeler — Dry-Run Summary',
        '',
        f'**Mode:** dry_run',
        f'**Input CSV:** `{args.input_csv}`',
        f'**Total rows in CSV:** {len(all_rows)}',
        f'**Start index:** {args.start_index}',
        f'**Max rows:** {args.max_rows if args.max_rows is not None else "all"}',
        f'**Row IDs filter:** {args.row_ids or "(none)"}',
        f'**Include labeled:** {args.include_labeled}',
        f'**Rows selected:** {len(selected)}',
        f'**Rows with leakage:** {leakage_count}',
        '',
        '## Safety',
        '',
        '- No API calls made (dry_run mode)',
        '- No Azure SDK imported or called',
        '- Gold metadata (`is_correct_offline_metadata`) excluded from all prompts',
        '- Manual labels and notes excluded from all prompts',
        '- No dataset rows sent to any external service',
        '',
    ]
    if leakage_count > 0:
        lines += [
            '## WARNING: LEAKAGE DETECTED',
            '',
            f'{leakage_count} row(s) have leakage terms in their prompts.',
            'Review `azure_label_requests.jsonl` before proceeding.',
            '',
        ]
    else:
        lines += ['## Leakage check: CLEAN — no leakage terms found in any prompt', '']

    lines += [
        '## Output files',
        '',
        '- `azure_label_requests.jsonl` — prompt requests',
        '- `run_manifest.json` — run parameters',
        '- `label_summary.md` — this file',
        '',
    ]

    with (output_dir / 'label_summary.md').open('w') as f:
        f.write('\n'.join(lines))

    print(f'[dry_run] {len(selected)} rows selected, {leakage_count} with leakage.')
    print(f'[dry_run] Outputs: {output_dir}')
    if leakage_count:
        print(f'[dry_run] WARNING: {leakage_count} rows have prompt leakage — check before API run.')

    return 0


# ---------------------------------------------------------------------------
# API mode
# ---------------------------------------------------------------------------

def run_api(args, all_rows, output_dir):
    # Validate env vars before importing SDK
    api_key = os.environ.get('AZURE_OPENAI_API_KEY', '')
    endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT', '')
    if not api_key:
        print('ERROR: AZURE_OPENAI_API_KEY is not set.', file=sys.stderr)
        return 1
    if not endpoint:
        print('ERROR: AZURE_OPENAI_ENDPOINT is not set.', file=sys.stderr)
        return 1

    # Late import — only in api mode
    try:
        from openai import OpenAI  # noqa: PLC0415
    except ImportError:
        print('ERROR: openai package not installed. Run: pip install openai', file=sys.stderr)
        return 1

    client = OpenAI(api_key=api_key, base_url=endpoint)
    deployment = args.deployment or os.environ.get('AZURE_OPENAI_DEPLOYMENT', '')
    if not deployment:
        print('ERROR: AZURE_OPENAI_DEPLOYMENT is not set and --deployment not provided.',
              file=sys.stderr)
        return 1

    selected = select_rows(
        all_rows,
        start_index=args.start_index,
        max_rows=args.max_rows,
        row_ids_set=set(args.row_ids.split(',')) if args.row_ids else set(),
        include_labeled=args.include_labeled,
    )

    # Resume: load already-normalized row_ids
    norm_path = output_dir / 'azure_label_responses_normalized.jsonl'
    raw_path = output_dir / 'azure_label_responses_raw.jsonl'
    hesitant_path = output_dir / 'hesitant_cases.jsonl'

    done_ids = set()
    if args.resume:
        existing = read_jsonl(norm_path)
        done_ids = {r['row_id'] for r in existing}
        if done_ids:
            print(f'[resume] Skipping {len(done_ids)} already-normalized rows.')

    pending = [r for r in selected if r.get('row_id', '') not in done_ids]
    print(f'[api] {len(pending)} rows to label (of {len(selected)} selected).')

    success_count = 0
    error_count = 0
    hesitant_cases = []

    for i, row in enumerate(pending):
        row_id = row.get('row_id', f'unknown_{i}')
        prompt = build_prompt(row)

        # Leakage guard
        leakage = validate_prompt_text(prompt)
        if leakage:
            print(f'[api] ABORT row {row_id}: prompt leakage detected: {leakage}',
                  file=sys.stderr)
            error_count += 1
            continue

        print(f'[api] ({i+1}/{len(pending)}) row_id={row_id}', end=' ', flush=True)
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=args.temperature,
                max_completion_tokens=256,
            )
            response_text = response.choices[0].message.content or ''
            finish_reason = response.choices[0].finish_reason

            # Save raw
            raw_record = {
                'row_id': row_id,
                'deployment': deployment,
                'response_text': response_text,
                'finish_reason': finish_reason,
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
            }
            append_jsonl(raw_path, raw_record)

            # Normalize
            normalized, err = normalize_response(row_id, deployment, response_text, finish_reason)
            if err:
                print(f'NORM_ERROR: {err}')
                error_count += 1
            else:
                append_jsonl(norm_path, normalized)
                success_count += 1
                print(f'label={normalized["relation_ready_label"]} '
                      f'confidence={normalized["confidence"]}')
                if normalized['is_hesitant']:
                    hesitant_cases.append({
                        **normalized,
                        'question': row.get('question', ''),
                        'candidate_answer': row.get('candidate_answer', ''),
                    })
                    append_jsonl(hesitant_path, hesitant_cases[-1])

        except Exception as exc:  # noqa: BLE001
            print(f'API_ERROR: {type(exc).__name__}: {exc}')
            error_count += 1

    # Write hesitant markdown
    _write_hesitant_md(output_dir, hesitant_cases)

    # Write label summary
    all_normalized = read_jsonl(norm_path)
    _write_label_summary(output_dir, args, all_normalized, success_count, error_count, deployment)

    # Write manifest
    manifest = {
        'mode': 'api',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'input_csv': str(args.input_csv),
        'total_rows_in_csv': len(all_rows),
        'start_index': args.start_index,
        'max_rows': args.max_rows,
        'row_ids_filter': args.row_ids or None,
        'include_labeled': args.include_labeled,
        'rows_selected': len(selected),
        'rows_labeled_this_run': success_count,
        'rows_errored_this_run': error_count,
        'rows_resumed': len(done_ids),
        'deployment': deployment,
        'temperature': args.temperature,
        'api_calls_made': success_count + error_count,
        'gold_metadata_excluded': True,
        'manual_labels_excluded': True,
    }
    with (output_dir / 'run_manifest.json').open('w') as f:
        json.dump(manifest, f, indent=2)

    print(f'\n[api] Done. success={success_count} errors={error_count} '
          f'hesitant={len(hesitant_cases)}')
    print(f'[api] Outputs: {output_dir}')
    return 0 if error_count == 0 else 1


def _write_hesitant_md(output_dir, hesitant_cases):
    lines = [
        '# Hesitant Cases — Azure RelationReady Labeler',
        '',
        f'Total hesitant: {len(hesitant_cases)}',
        '',
    ]
    for case in hesitant_cases:
        lines += [
            f'## row_id: {case["row_id"]}',
            '',
            f'**Label:** {case["relation_ready_label"]}  '
            f'**Confidence:** {case["confidence"]}  '
            f'**Axis:** {case["first_error_axis"]}',
            '',
            f'**Question:** {case.get("question", "")}',
            '',
            f'**Answer:** {case.get("candidate_answer", "")}',
            '',
            f'**Hesitation reason:** {case["hesitation_reason"]}',
            '',
            f'**Rationale:** {case["rationale"]}',
            '',
            '---',
            '',
        ]
    with (output_dir / 'hesitant_cases.md').open('w') as f:
        f.write('\n'.join(lines))


def _write_label_summary(output_dir, args, all_normalized, success_count, error_count, deployment):
    from collections import Counter
    label_counts = Counter(r['relation_ready_label'] for r in all_normalized)
    axis_counts = Counter(r['first_error_axis'] for r in all_normalized if r['first_error_axis'])
    hesitant_count = sum(1 for r in all_normalized if r.get('is_hesitant'))

    lines = [
        '# Azure RelationReady Labeler — Label Summary',
        '',
        f'**Deployment:** {deployment}',
        f'**Input CSV:** `{args.input_csv}`',
        f'**This run:** success={success_count} errors={error_count}',
        f'**Total normalized rows:** {len(all_normalized)}',
        '',
        '## Label distribution',
        '',
    ]
    for label in ('ready', 'not_ready', 'uncertain', 'gold_inconsistent'):
        lines.append(f'- {label}: {label_counts.get(label, 0)}')
    lines += [
        '',
        '## First-error-axis distribution (not_ready rows)',
        '',
    ]
    for axis, cnt in axis_counts.most_common():
        lines.append(f'- {axis}: {cnt}')
    lines += [
        '',
        f'## Hesitant cases: {hesitant_count}',
        '',
        '## Safety',
        '',
        '- Gold metadata excluded from all prompts',
        '- Manual labels and notes excluded from all prompts',
        '',
    ]
    with (output_dir / 'label_summary.md').open('w') as f:
        f.write('\n'.join(lines))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(description='Azure OpenAI assisted labeler for RelationReady rows.')
    p.add_argument('--input-csv', required=True,
                   help='Path to positive_candidate_batch.csv')
    p.add_argument('--output-dir', required=True,
                   help='Directory to write outputs into (created if absent)')
    p.add_argument('--start-index', type=int, default=0,
                   help='First row index to process (default: 0)')
    p.add_argument('--max-rows', type=int, default=None,
                   help='Maximum number of rows to process')
    p.add_argument('--row-ids', default=None,
                   help='Comma-separated row_ids to process (takes precedence over start-index)')
    p.add_argument('--mode', choices=['dry_run', 'api'], default='dry_run',
                   help='dry_run: no API calls; api: live Azure calls')
    p.add_argument('--allow-api', action='store_true',
                   help='Required for api mode; prevents accidental live calls')
    p.add_argument('--deployment', default=None,
                   help='Azure deployment name (default: AZURE_OPENAI_DEPLOYMENT env var)')
    p.add_argument('--temperature', type=float, default=0.0,
                   help='Sampling temperature (default: 0)')
    p.add_argument('--resume', action='store_true',
                   help='Skip rows already present in normalized output (api mode only)')
    p.add_argument('--include-labeled', action='store_true',
                   help='Include rows that already have relation_ready_label_manual set')
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(f'ERROR: input CSV not found: {input_path}', file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rows = read_csv_rows(input_path)

    if args.mode == 'api':
        if not args.allow_api:
            print('ERROR: api mode requires --allow-api flag.', file=sys.stderr)
            return 1
        return run_api(args, all_rows, output_dir)

    return run_dry_run(args, all_rows, output_dir)


if __name__ == '__main__':
    sys.exit(main())
