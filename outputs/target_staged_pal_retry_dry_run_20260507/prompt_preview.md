# Target-staged PAL dry-run — prompt preview

_Manifest:_ `/home/soroush/research-next-wt/manifests/target_staged_pal_retry_primary_11_20260507.json`

## Prompt 1

```text
You solve short math word problems. Use only arithmetic and the problem facts.

Use nothing outside the PROBLEM block below—no hints from other runs, no other datasets or methods.

Your reply MUST use these six labeled sections in this exact order (each label starts at the beginning of a line).
After CHECKS, the PYTHON section holds code only.

TARGET:
(one line: the exact quantity the problem asks for, paraphrased from the problem text)

UNITS:
(one line: the unit or answer type, e.g. count, dollars, minutes, weeks)

GIVEN_QUANTITIES:
(bullet lines; each starts with "- " then a number and a short meaning from the problem)

SUBGOALS:
(bullet lines; each starts with "- "; ordered intermediate values to compute before the final result)

CHECKS:
(bullet lines; each starts with "- "; what the final number must represent and quick sanity rules)

PYTHON:
(either a fenced Python block or plain Python; it must print exactly one numeric final line)

PROBLEM:
A cobra, which has 70 spots, has twice as many spots as a mamba. If there are 40 cobras and 60 mambas in a snake park, what is half the number of spots they all have combined?


```

## Prompt 2 (excerpt)

```text
You solve short math word problems. Use only arithmetic and the problem facts.

Use nothing outside the PROBLEM block below—no hints from other runs, no other datasets or methods.

Your reply MUST use these six labeled sections in this exact order (each label starts at the beginning of a line).
After CHECKS, the PYTHON section holds code only.

TARGET:
(one line: the exact quantity the problem asks for, paraphrased from the problem text)

UNITS:
(one line: the unit or answer type, e.g. count, dollars, minutes, weeks)

GIVEN_QUANTITIES:
(bullet lines; each starts with "- " then a number and a short meaning from the problem)

SUBGOALS:
(bullet lines; each starts with "- "; ordered intermediate values to compute before the final result)

CHECKS:
(bullet lines; each starts with "- "; what the final number must represent and quick sanity rules)

PYTHON:
(either a fenced Python block or plain Python; it must print exactly one numeric final line)

PROBLEM:
Helga was the fastest clog dancer in all of Slovenia. With both hands at her sides, she could tap her right foot at a rate of 300 taps per minute, while simultaneously tapping her left foot at a rate of 250 taps per minute.  When she raised her arms, her tap rate slowed down to 200 taps per minute with each foot.  If she dances a total of 5 minutes, with her arms raised during only 2 of those minutes, what would be the combined total number of times that she taps both of her feet?


... [truncated]
```
