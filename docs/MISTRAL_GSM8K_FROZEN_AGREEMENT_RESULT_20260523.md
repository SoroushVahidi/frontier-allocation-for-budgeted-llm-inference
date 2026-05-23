# Mistral GSM8K Frozen Agreement Result (2026-05-23)

**Status:** complete and integrity-checked.

- **Provider/model:** Mistral / `mistral-small-latest`
- **Endpoint:** `https://api.mistral.ai/v1/chat/completions`
- **Run roots:** raw `outputs/mistral_frozen_agreement_only_2of3_validation_20260523T145416Z`, result `outputs/mistral_frozen_agreement_only_2of3_live_result_20260523`
- **Active jobs left untouched:** Cohere canonical Final-300 and Cerebras GSM8K were running and were not modified.

## Integrity

- `1200/1200` scored
- `0` missing
- `0` failed
- `0` duplicate rows
- `300/300` examples fully complete
- recovery passes used: `0`
- failure taxonomy: empty

## Rate-limit behavior

- Observed retry events: `578`
- All observed retry events were `HTTP_429`
- No hard API/auth/model failures appeared in the preserved artifacts
- No parse failures appeared for any method

Support packet: `outputs/mistral_frozen_agreement_only_2of3_live_result_20260523/mistral_rate_limit_support_packet.md`

## Full-coverage same-provider results

| policy | accuracy | notes |
|---|---:|---|
| frontier | 235/300 = 78.33% | baseline |
| L1 | 217/300 = 72.33% | below frontier |
| S1 | 269/300 = 89.67% | best single source |
| TALE | 189/300 = 63.00% | lowest |
| agreement-only 2-of-3 | 256/300 = 85.33% | deferred 58, kept frontier 242 |
| external-3 with fallback | 256/300 = 85.33% | same as agreement-only |
| pooled-4 with fallback | 251/300 = 83.67% | deferred 18, kept frontier 282 |

## Pairwise comparisons

- agreement-only vs frontier: `34/13/253` win/loss/tie; CI `+7.0 pp [2.33, 11.67]`
- agreement-only vs L1: `40/1/259`; CI `+13.0 pp [9.33, 17.00]`
- agreement-only vs pooled-4: CI `+1.67 pp [-2.33, 5.33]` — point estimate favors agreement-only, but the CI crosses zero

## S1 dominance

- `s1_correct_frontier_wrong = 42`
- `s1_correct_l1_and_tale_wrong = 30`
- `only_s1_correct = 9`
- `s1_wrong_others_correct = 3`
- `agreement_wrong_while_s1_correct = 19`
- `kept_frontier_when_s1_correct_and_frontier_wrong = 8`
- parse failures: `0` for all methods

## Interpretation

S1 is the strongest single source on this Mistral run. The advantage is not explained by parser failures, because none were observed. Agreement-only beats frontier and L1 on this run, but its edge over pooled-4 is not statistically established here.

Safest takeaway: this run supports a provider/model-specific source-ranking shift toward S1 for Mistral, but not a promoted provider-specific S1 rule without separate validation.
