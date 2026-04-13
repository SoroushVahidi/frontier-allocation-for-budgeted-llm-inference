# Metareasoning source-verification note (2026-04-13)

This note records a conservative verification pass over several classical metareasoning papers so later manuscript writing can cite them accurately without overclaiming.

## 1. Why this note matters

Classical metareasoning papers are highly relevant to the project, but they mix formal definitions, special-case analyses, and conceptual discussion. It is therefore important to distinguish clearly between:
- what is formally defined
- what is formally proved
- what is conceptual framing only

This note records the safest current interpretation.

## 2. Russell & Wefald (1991) — safest use

### Safest citation role
Use this paper primarily for a **formal value-of-computation style definition** and the general decision-theoretic framing of metareasoning.

### Safe claim
This paper provides a general formal framework for treating computations as actions whose utility depends on their effect on object-level decision quality and their computational cost.

### Do not overclaim
Do **not** cite this paper as proving a broad myopic-optimality theorem for our setting unless the original text is checked again in detail for a specific special case.

### Best manuscript use
- formal VOC language
- metareasoning as decision-theoretic control of internal computation
- motivation for learning marginal value of computation rather than static branch quality

## 3. Horvitz (1987) — safest use

### Safest citation role
Use this paper for the idea that reasoning quality should be evaluated together with the cost of computation, including delay or resource costs.

### Safe claim
This paper formalizes decision making under computational resource constraints and supports the view that the value of additional inference must be weighed against its computational cost.

### Do not overclaim
Do **not** cite it as proving a general bounded-optimality theorem.

### Best manuscript use
- metareasoning has cost
- comprehensive utility includes both object-level gain and inference cost
- fixed-budget allocation should not ignore controller overhead

## 4. Russell & Subramanian (1995) / bounded optimality line — safest use

### Safest citation role
Use this line for the **bounded-optimality oracle notion**.

### Safe claim
The bounded-optimality perspective supports evaluating an agent relative to the best achievable policy under the same computational architecture or resource constraints, rather than relative to an unrealistic unconstrained ideal.

### Do not overclaim
Do **not** conflate bounded optimality with VOC definitions. These serve different roles.

### Best manuscript use
- define the correct oracle comparison under a fixed budget
- justify comparing the learned allocator to the best policy under the same resource limit

## 5. Horvitz (2001) — safest use

### Safest citation role
Use this paper for broader continual-computation framing and for the idea that computational resources may need to be allocated across present and future decision needs.

### Safe claim
This paper extends classical resource-bounded reasoning ideas to settings where computation must be scheduled continually over time.

### Do not overclaim
Do **not** cite it as the main source of a general theorem we have not directly verified.

### Best manuscript use
- broader context for continual allocation of computational effort
- conceptual bridge to resource scheduling and ongoing inference control

## 6. Safest manuscript citation mapping

The current safest mapping is:

- **Formal VOC definition / metareasoning language** -> Russell & Wefald (1991)
- **Metareasoning has cost / inference cost matters** -> Horvitz (1987)
- **Bounded-optimality-style oracle notion** -> Russell & Subramanian (1995)
- **Broader continual-computation context** -> Horvitz (2001)

## 7. Common overclaims to avoid

Avoid the following unless the original papers are rechecked very carefully.

### 7.1 Overclaiming myopic optimality
Do not say Russell & Wefald (1991) proves a general myopic optimality theorem for our branch-allocation setting.

### 7.2 Overclaiming bounded optimality from Horvitz (1987)
Do not attribute a full bounded-optimality theorem to Horvitz (1987).

### 7.3 Treating conceptual framing as theorem statements
Many valuable classical insights are conceptual or definitional rather than theorem statements. Use them honestly as such.

### 7.4 Merging different classical ideas into one citation
VOC, bounded optimality, and continual computation are related but distinct. They should not be compressed into one umbrella citation without care.

## 8. Best current use for our project

The safest current use of these metareasoning papers is:

1. define the project locally in terms of **marginal value of computation**
2. define the oracle globally in terms of **bounded optimality under the same compute budget**
3. explicitly acknowledge that **metareasoning itself consumes budget**

This is already strong enough to support manuscript framing without forcing theorem claims that the source papers do not clearly make.

## 9. Working manuscript sentence

A safe working sentence is:

> We interpret adaptive test-time branch allocation as a metareasoning problem: each candidate internal computation has a potential value for improving the final decision, but also incurs computational cost. This perspective motivates learning a marginal value-of-computation signal for branch allocation and evaluating policies relative to a bounded-optimal budget-constrained oracle.

## 10. Status

This note should be revisited later if the manuscript reaches the citation-polishing stage and exact theorem statements from the original sources are needed verbatim.