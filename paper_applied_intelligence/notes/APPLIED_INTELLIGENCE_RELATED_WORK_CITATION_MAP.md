APPLIED_INTELLIGENCE_RELATED_WORK_CITATION_MAP
=============================================

1) Test-time compute and budgeted LLM reasoning
- Keys: snell2024scaling, muennighoff2025s1, wei2022cot, wang2023selfconsistency, yao2023tot, besta2024got
- 2–3 lines: Discuss matched-budget evaluation and trade-offs between spending additional inference compute vs smarter selection. Emphasize post-generation selection (FTA) differs from generation-time scaling: it uses runtime-visible metadata without extra calls. Warn: several works are arXiv/preprint; use peer-reviewed venue labels when available.

2) Answer aggregation and verifier-guided selection
- Keys: cobbe2021training, lightman2024verify, madaan2023selfrefine, wang2023selfconsistency
- 2–3 lines: Cover verifiers, self-consistency, and iterative self-correction approaches that rerank or verify candidate answers. Position FTA as a lightweight, gold-free selection layer versus trained verifiers.

3) Dynamic ensemble selection and algorithm selection
- Keys: dietterich2000ensemble, rice1976algorithm, cruz2015metades, ko2008dynamic, hospedales2022metalearning, zhu2023automldes
- 2–3 lines: Survey classic algorithm-selection and modern meta-learning approaches for choosing models or ensemble members per instance. Note differences: FTA uses runtime trace signals rather than learned selectors.

4) Selective prediction, calibration, and learned deferral
- Keys: geifman2017selectiveclassificationdeepneural, guo2017calibration, mao2023defer, efron1979bootstrap
- 2–3 lines: Explain abstention/fallback frameworks and calibration literature that justify conservative overrides. Highlight statistical testing and bootstrap methods for evaluation.

5) Cost-aware LLM routing and cascades
- Keys: chen2023frugalgpt, dohan2022cascades, ong2024routellm, zhang2025ecorouter, ding2025bestroute
- 2–3 lines: Discuss cascades, routing policies, and cost-aware selection across models/stages. Emphasize caution when comparing methods under matched budgets; some recent works are conference posters or preprints—verify metadata before citing.

References to avoid / verify
- Avoid using "Multi-Step Dynamic Ensemble Selection to Estimate Software Effort" as Applied Intelligence evidence.
- Defer MUSE and Beyond Majority Voting until full author/venue metadata are verified locally.
- Mark any ICLR/NeurIPS/ICML-2025/2026 claims as "poster/under verification" unless confirmed.

Practical notes for rewrite
- For each subsection list 4–8 recommended keys (above); prefer peer-reviewed venue labels when available and mark arXiv preprints explicitly.
- Flag keys that are preprints in refs.bib (see arxiv_entries.txt) and do not present them as peer-reviewed.
- Keep citation density moderate: 4–6 core citations per subsection is sufficient.

