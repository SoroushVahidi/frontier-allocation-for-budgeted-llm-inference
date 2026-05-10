# Retry-on-empty-code Patch Evidence

## Readiness from 31-case audit

- Retry-eligible: **16/31**
- L1_P1 retry-eligible: **14/14**

## 5-case smoke

- Retry ran: **4/5**
- Fixes vs prior PAL: **3**
- Breaks vs prior PAL: **0**
- Exact: **3/5**

## 11-case follow-up

- Retry ran: **4/11**
- Fixes vs prior PAL: **3**
- Breaks vs prior PAL: **0**
- Exact: **0.273**

## Aggregate across smoke + follow-up

- Evaluated: **16**
- Fixes: **6**
- Breaks: **0**
- Net: **+6**
- Retry exec-OK rate: **0.375**

Conclusion: keep retry-on-empty-code; it is **beneficial but still brittle**.

## Updated estimated effect boundary

On the 31 external-only losses, live reevaluation found **6 fixes** on the targeted retry-eligible subset. This is **not** an unbiased global-accuracy estimate; it is targeted evidence on external-only retry-eligible failures.
