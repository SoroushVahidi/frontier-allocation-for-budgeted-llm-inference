## Headline

selector closes most of the gap

## Accuracy table

- original DR-v2: 0.400
- DR-v2 + selected selector: 0.580
- external_l1_max: 0.540

## Pairwise table

- both correct: 25
- both wrong: 19
- selected only correct: 4
- external only correct: 2

## Bottleneck table

- both_correct: 18
- selector_fixed: 10
- both_wrong: 19
- external_only_correct: 1
- selector_broke: 1
- selected_only_correct: 1

## Safety caveats

- bounded pilot run.
- selected selector chosen on recovery evidence and not runtime promoted.
- no external_l1_max defeat claim unless supported by metrics.
- current-correct break risk may be nonzero.
