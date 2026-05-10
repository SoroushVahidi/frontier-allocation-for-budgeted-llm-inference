# External-only failure notes

Detailed notes for external_correct_pal_wrong cases.

## openai_gsm8k_162
- External answer: `50` (exact=1)
- PAL answer: `60` (exact=0)
- PAL code_present/safety_ok/exec_ok: 1/1/1
- Gold in PAL tree / discovery3: 0/0
- Label: L1_P4_exec_succeeded_wrong
- Pattern: PAL execution succeeds and returns a concrete value, but computed value is numerically wrong.

## openai_gsm8k_166
- External answer: `15` (exact=1)
- PAL answer: `1` (exact=0)
- PAL code_present/safety_ok/exec_ok: 0/0/0
- Gold in PAL tree / discovery3: 0/0
- Label: L1_P1_code_absent
- Pattern: PAL produced no executable code/JSON answer; selector fell back to a non-gold candidate.
- PAL error: `ValueError` / ``

## openai_gsm8k_168
- External answer: `35` (exact=1)
- PAL answer: `40` (exact=0)
- PAL code_present/safety_ok/exec_ok: 1/1/1
- Gold in PAL tree / discovery3: 0/1
- Label: L1_P4_exec_succeeded_wrong
- Pattern: PAL execution succeeds and returns a concrete value, but computed value is numerically wrong.

## openai_gsm8k_180
- External answer: `8` (exact=1)
- PAL answer: `25` (exact=0)
- PAL code_present/safety_ok/exec_ok: 1/1/1
- Gold in PAL tree / discovery3: 0/0
- Label: L1_P4_exec_succeeded_wrong
- Pattern: PAL execution succeeds and returns a concrete value, but computed value is numerically wrong.

## openai_gsm8k_183
- External answer: `40` (exact=1)
- PAL answer: `5760` (exact=0)
- PAL code_present/safety_ok/exec_ok: 1/1/1
- Gold in PAL tree / discovery3: 0/0
- Label: L1_P4_exec_succeeded_wrong
- Pattern: PAL execution succeeds and returns a concrete value, but computed value is numerically wrong.

## openai_gsm8k_184
- External answer: `525` (exact=1)
- PAL answer: `527.6381909547739` (exact=0)
- PAL code_present/safety_ok/exec_ok: 1/1/1
- Gold in PAL tree / discovery3: 0/0
- Label: L1_P4_exec_succeeded_wrong
- Pattern: PAL execution succeeds and returns a concrete value, but computed value is numerically wrong.

## openai_gsm8k_190
- External answer: `420` (exact=1)
- PAL answer: `720` (exact=0)
- PAL code_present/safety_ok/exec_ok: 1/1/1
- Gold in PAL tree / discovery3: 0/0
- Label: L1_P4_exec_succeeded_wrong
- Pattern: PAL execution succeeds and returns a concrete value, but computed value is numerically wrong.

## openai_gsm8k_204
- External answer: `4` (exact=1)
- PAL answer: `-240` (exact=0)
- PAL code_present/safety_ok/exec_ok: 1/1/1
- Gold in PAL tree / discovery3: 1/1
- Label: L1_P5_correct_candidate_not_selected
- Pattern: Gold-equivalent answer appears in PAL candidate tree, but final selector/tiebreak chose a different answer.

## openai_gsm8k_262
- External answer: `23` (exact=1)
- PAL answer: `32` (exact=0)
- PAL code_present/safety_ok/exec_ok: 1/1/1
- Gold in PAL tree / discovery3: 0/0
- Label: L1_P4_exec_succeeded_wrong
- Pattern: PAL execution succeeds and returns a concrete value, but computed value is numerically wrong.

## openai_gsm8k_264
- External answer: `50` (exact=1)
- PAL answer: `-110` (exact=0)
- PAL code_present/safety_ok/exec_ok: 1/1/1
- Gold in PAL tree / discovery3: 0/0
- Label: L1_P4_exec_succeeded_wrong
- Pattern: PAL execution succeeds and returns a concrete value, but computed value is numerically wrong.
