## Headline

Results inconclusive because full Cohere score coverage is unavailable.

## Accuracy table

- original DR-v2: 0.400
- self-consistency majority vote: 0.580
- Cohere outcome-verifier selected selector: 0.580
- external_l1_max: 0.540

## Fix/break table

- self-consistency: fixes=9 breaks=0 net=9
- cohere outcome-verifier: fixes=9 breaks=0 net=9

## Pairwise table

- both correct: 27
- both wrong: 19
- self-consistency only correct: 2
- Cohere only correct: 2

## Safety/break-risk table

- original-correct cases: 20
- self-consistency breaks: 0 (0.000)
- cohere breaks: 0 (0.000)

## Bottleneck table

- self-consistency wrong: discovery=14 selector=7
- cohere wrong: discovery=14 selector=7
