## Headline

selector improves DR-v2 but external_l1_max remains ahead

## Accuracy table

- original DR-v2: 0.440
- DR-v2 + selected selector: 0.600
- external_l1_max: 0.640

## Pairwise table

- both correct: 14
- both wrong: 8
- selected only correct: 1
- external only correct: 2

## Bottleneck table

- both_correct: 10
- selector_fixed: 5
- both_wrong: 8
- external_only_correct: 1
- selector_broke: 1

## Safety caveats

- bounded pilot run.
- selected selector chosen on recovery evidence and not runtime promoted.
- no external_l1_max defeat claim unless supported by metrics.
- current-correct break risk may be nonzero.
