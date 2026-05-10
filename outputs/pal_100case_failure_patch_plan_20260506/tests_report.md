# Tests report

Executed (no-API):

```bash
pytest -q tests/test_pal_executor.py tests/test_pal_variant.py tests/test_output_layer_frontier_surfacing.py tests/test_api_branch_generator_json_parsing.py
```

Result: **74 passed, 0 failed**.

Coverage notes:
- PAL executor now accepts safe `int`/`float` conversion.
- Existing security rejections still pass (imports/file/network/system/eval/exec/open/dunder/attributes etc.).
- PAL variant/output-layer/parser regressions unchanged.
