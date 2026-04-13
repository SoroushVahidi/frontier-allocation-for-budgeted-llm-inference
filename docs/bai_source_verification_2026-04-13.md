# Fixed-budget BAI source-verification note (2026-04-13)

This note records a conservative verification pass over the classical best-arm identification (BAI) literature so later manuscript writing can cite the field accurately without overclaiming.

## 1. Why this note matters

The project increasingly uses fixed-budget best-arm identification as a classical stochastic backbone. However, the BAI literature separates:
- fixed-budget and fixed-confidence settings
- algorithmic upper bounds and lower bounds
- simple regret and identification error formulations

These distinctions matter for clean manuscript framing.

## 2. Audibert, Bubeck, and Munos (2010) — safest use

### Safest citation role
Use this paper as the main classical source for **fixed-budget best-arm identification algorithms and guarantees**.

### Safe claim
This paper studies best-arm identification in stochastic multi-armed bandits under a fixed sampling budget and provides algorithms such as UCB-E and Successive Rejects, together with exponential error bounds governed by gap-dependent complexity quantities.

### What it is safest for
- canonical fixed-budget BAI framing
- Successive Rejects style elimination under a hard budget
- gap-dependent complexity quantities such as H1 and H2
- exponential identification-error guarantees under a fixed number of samples

### Do not overclaim
Do not cite this paper as providing the final optimal fixed-budget characterization in full generality. It is foundational and highly useful, but not the last word on all fixed-budget lower bounds.

## 3. Gabillon, Ghavamzadeh, and Lazaric (2012) — safest use

### Safest citation role
Use this paper for a **unified treatment of fixed-budget and fixed-confidence BAI**.

### Safe claim
This paper gives a unified gap-based approach covering both fixed-budget and fixed-confidence settings, with corresponding complexity terms and algorithms.

### What it is safest for
- one paper covering both major BAI settings
- epsilon / top-m style extensions beyond the simplest best-arm setting
- complexity terms that govern both budgeted and confidence-based guarantees

### Do not overclaim
Do not treat this paper as the canonical fixed-budget lower-bound source. Its value is primarily in the unified algorithmic and analytical perspective.

## 4. Garivier and Kaufmann (2016) — safest use

### Safest citation role
Use this paper as the main source for **fixed-confidence lower-bound and asymptotic optimality ideas**.

### Safe claim
This paper provides a sharp fixed-confidence characterization through a complexity quantity based on an optimization over sampling proportions and alternatives, and gives an asymptotically optimal algorithm in that regime.

### What it is safest for
- fixed-confidence lower bounds
- oracle sampling proportions
- information-theoretic complexity language
- asymptotically optimal allocation ideas

### Do not overclaim
Do not cite this as a fixed-budget theorem source. It is highly relevant conceptually, but its formal home is the fixed-confidence setting.

## 5. Safest manuscript citation mapping

The current safest mapping is:

- **Canonical fixed-budget BAI algorithmic backbone** -> Audibert, Bubeck, and Munos (2010)
- **Unified fixed-budget / fixed-confidence perspective** -> Gabillon, Ghavamzadeh, and Lazaric (2012)
- **Fixed-confidence lower-bound / oracle allocation perspective** -> Garivier and Kaufmann (2016)

## 6. Best current use for our project

The safest way to use BAI in the manuscript is:

1. treat fixed-budget BAI as the closest classical stochastic analog of budgeted branch allocation
2. use fixed-budget algorithms and gap-dependent complexity terms as inspiration for adaptive elimination and allocation
3. borrow lower-bound and oracle-allocation ideas from fixed-confidence BAI carefully, without claiming the original results are fixed-budget theorems

## 7. Common overclaims to avoid

### 7.1 Confusing fixed budget with fixed confidence
These are related but distinct regimes. The paper should keep them separate.

### 7.2 Treating simple regret minimization as ordinary cumulative regret minimization
The BAI literature is about pure exploration and final identification quality, not the usual cumulative regret objective.

### 7.3 Claiming parameter-free optimality too broadly
Some classical algorithms are elegant and practical but do not solve all fixed-budget optimality questions in a fully parameter-free sense.

### 7.4 Importing KL-based lower bounds into our setting without caution
KL-style lower-bound ideas are very useful conceptually, but our branch-allocation setting has evolving, correlated, partially observed branches rather than standard stationary arms.

## 8. Best current adaptation idea

The strongest current adaptation path is not to directly reduce the whole project to classical BAI, but to borrow:
- the **fixed-budget identification perspective**
- the idea of **adaptive elimination under budget**
- the use of **gap-dependent hardness quantities**
- and the idea that **local sampling/allocation mistakes accumulate into final identification error**

This fits naturally with the current theorem target of relating local branch-misranking to global allocation regret or success loss.

## 9. Working manuscript sentence

A safe working sentence is:

> Classical fixed-budget best-arm identification provides the closest stochastic abstraction of our setting: a limited budget must be allocated across uncertain options so as to maximize the probability of identifying the best one. Our branch-allocation problem departs from classical BAI because branches evolve as they are explored, but the fixed-budget identification viewpoint remains highly informative.

## 10. Status

This note should be revisited later if the manuscript needs exact theorem statements or verbatim lower-bound formulations from the original BAI papers.