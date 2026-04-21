# BEST-Route import package templates

Repository-native BEST-Route import-package templates live at:

- `external/best_route_microsoft/package_templates/`

Each dataset package contains the exact validator-required files:

- `metadata.json`
- `results.csv`

Current template packages:

- `external/best_route_microsoft/package_templates/math500/`
- `external/best_route_microsoft/package_templates/aime2024/`
- `external/best_route_microsoft/package_templates/olympiadbench/`
- `external/best_route_microsoft/package_templates/gsm8k/` (optional consistency template)

## Generator script

Use:

```bash
python scripts/generate_best_route_import_package_templates.py --include-gsm8k
```

You can change datasets and output location:

```bash
python scripts/generate_best_route_import_package_templates.py \
  --datasets math500,aime2024,olympiadbench \
  --output-root external/best_route_microsoft/package_templates \
  --force
```

## Placeholder policy

Templates are validator-oriented stubs, not real BEST-Route export artifacts.
They intentionally include `TEMPLATE_*` values to make replacement mandatory before
any artifact is treated as an imported result.

Replace at minimum:

- `metadata.json`
  - `candidate_arms[*].model_name`
  - `provenance.source_uri`
  - `provenance.artifact_id`
  - `provenance.commit_or_version_if_available`
  - any additional provenance fields you need for auditability
- `results.csv`
  - `router_strategy`
  - `accuracy`
  - `avg_token_cost`
  - `artifact_id`
  - `commit_or_version`

Keep fixed unless your validator contract changes:

- dataset label (`dataset.name` in metadata and `dataset` in CSV)
- split (`test`)
- budgets (`budget_1`, `budget_2`)
- comparability scope (`adjacent_only`)
- arm-space format containing at least one `bo1` and one `bo>1` arm marker

## Validate a finished package

After replacing placeholders with real BEST-Route outputs:

```bash
python scripts/verify_best_route_import.py \
  --results-path external/best_route_microsoft/package_templates/math500 \
  --expected-dataset math500 \
  --expected-split test \
  --expected-budgets 1,2
```

```bash
python scripts/verify_best_route_import.py \
  --results-path external/best_route_microsoft/package_templates/aime2024 \
  --expected-dataset aime2024 \
  --expected-split test \
  --expected-budgets 1,2
```

```bash
python scripts/verify_best_route_import.py \
  --results-path external/best_route_microsoft/package_templates/olympiadbench \
  --expected-dataset olympiadbench \
  --expected-split test \
  --expected-budgets 1,2
```

```bash
python scripts/verify_best_route_import.py \
  --results-path external/best_route_microsoft/package_templates/gsm8k \
  --expected-dataset gsm8k \
  --expected-split test \
  --expected-budgets 1,2
```
