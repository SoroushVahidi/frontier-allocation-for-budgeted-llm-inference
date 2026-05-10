# Next validation recommendation

## Decision

C. analyze/patch the 20 PAL failures first

## Why

- The +5 pp paired lift is competitive and directionally positive, but discordant-pair evidence (p=0.3018) and paired-diff uncertainty (bootstrap CI -2.00% to 13.00%) are not strong enough for a definitive superiority claim.
- PAL has identifiable fixable failure classes among 20 PAL-wrong cases (code absent/unsafe/exec failed/selection misses).
- Fixing these concrete issues can increase PAL reliability before spending on a larger expensive sample.

## Not chosen now

- Larger paired API run is deferred until targeted PAL failure fixes are implemented and no-API regression checks pass.
