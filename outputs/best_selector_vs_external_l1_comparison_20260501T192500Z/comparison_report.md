## Headline

comparison inconclusive due to too few cases / missing verifier scores

## Accuracy table

- original DR-v2: 0.570
- DR-v2 + selected selector: 0.570
- external_l1_max: 0.680

## Pairwise table

- both correct: 52
- both wrong: 27
- selected only correct: 5
- external only correct: 16

## Bottleneck table

- both_correct: 52
- external_only_correct: 16
- both_wrong: 27
- selected_only_correct: 5

## Safety caveats

- bounded pilot run.
- selected selector chosen on recovery evidence and not runtime promoted.
- no external_l1_max defeat claim unless supported by metrics.
- current-correct break risk may be nonzero.
