# Hugging Face dataset access check

Token env presence (presence/absence only):
- HF_TOKEN: present
- HUGGINGFACE_HUB_TOKEN: absent

Checked datasets:
- openai/gsm8k
- EleutherAI/hendrycks_math
- Idavidrein/gpqa (gated)
- Hothan/OlympiadBench
- livecodebench/code_generation_lite (optional)

## Results
- ✅ openai/gsm8k loaded (test, config=main)
- ✅ EleutherAI/hendrycks_math loaded (test, config=algebra)
- ✅ Idavidrein/gpqa loaded (train, config=gpqa_diamond)
- ✅ Hothan/OlympiadBench loaded (train, config=OE_TO_maths_en_COMP)
- ⚠️ livecodebench/code_generation_lite failed: RuntimeError: Dataset scripts are no longer supported, but found code_generation_lite.py

## GPQA loader-path verdict
- datasets loader success: True
- pandas hf:// fallback success: True
- loader path used: datasets
- final GPQA accessible verdict: True

Raw dataset files are not stored in git; this check only writes JSON/CSV/MD summaries.
