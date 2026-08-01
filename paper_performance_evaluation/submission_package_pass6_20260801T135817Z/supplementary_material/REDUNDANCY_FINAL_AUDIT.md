# Redundancy Final Audit

Date: 2026-08-01

Scope: Pass 6 redundancy and organization audit for the Performance Evaluation
conversion. Scientific values, tables, and evidence boundaries were preserved.

## Canonical Locations

| Point | Canonical location | Consolidation rule |
| --- | --- | --- |
| Nominal budget vs realized resources | Abstract, Section 3, Section 9 | Later mentions use short cross-references. |
| Frontier/FTA are instruments, not promoted algorithms | Introduction and Section 4 | Removed repeated "case-study" phrasing elsewhere. |
| Incomplete token/USD telemetry | Section 9 | Limitations now summarizes without restating ratios. |
| Single-cell self-consistency scope | Section 6.3 and Appendix O | Abstract and introduction no longer repeat the 276/300 result. |
| Adapter fidelity | Section 5.3 and Appendix C | Limitations now points to setup/appendix. |
| Blocked Fireworks x GPQA | Section 5.2 and Table 1 | Other mentions are short labels only. |
| Provider-transfer reversal | Section 8 | Abstract keeps a single compact summary; discussion gives practice implication. |
| Held-out selector choosing Pooled-4 | Section 7.3 and Table 6 | Abstract and caption do not restate all counts. |
| No general superiority claim | Introduction, Results framing, Limitations | Conclusion now states protocol contribution only. |

## Exact Consolidations

- Abstract: removed the held-out-selector sentence ("chooses Pooled-4 in all 15/15
  folds") and the single-cell SC sentence ("ties ... at 276/300"). These values
  remain in Sections 6.3 and 7.3.
- Abstract: removed repeated numerator detail for Pooled-4 and FTA while retaining
  percentages and McNemar p-value.
- Introduction: replaced four detailed result bullets with a protocol contribution
  paragraph and roadmap. The detailed values now appear only in Results/Provider
  Heterogeneity/Compute Accounting.
- Introduction: shortened the measurement-objects paragraph by removing the
  repeated SC 276/300 value.
- Results Table 1 caption: shortened trust-tier and blocked-cell prose; Section 5
  now carries those definitions.
- Held-out selector section: removed repeated row totals after Table 6. The prose
  now says the table gives the full result and states only the conclusion.
- Limitations: collapsed separate restatements of adapter fidelity, development
  adjacency, offline replay, and token/USD limitations into cross-references to
  Sections 5 and 9 plus Appendix chronology.
- Discussion: reduced the final paragraph to one semantic-separation sentence.
- Conclusion: replaced a result recap with a short synthesis of the accounting and
  attribution protocol.
- Appendix: shortened the opening roadmap, statistical-testing paragraph,
  reproducibility-records section, compute-detail prose, and historical SC preamble
  while retaining all reported numerical values.

## Terminology Audit

- Canonical term: `nominal budget`.
- Defined once: `logical entitlement`, `successful completion`, `retry`,
  `realized resource vector`, `identical-pool control`, and `protocol-blocked
  outcome`.
- Replaced visible uses of `nominal entitlement` with `nominal budget`.
- Retained `SC` only after first defining same-model self-consistency.
- No citation group contains more than four citations.

## Section Roles After Pass 6

- Introduction: motivation, gap, contribution, roadmap.
- Related Work: prior literature and differentiation.
- Evaluation Framework / Measurement Instruments: definitions and protocol objects.
- Experimental Protocol: datasets, providers, controls, provenance, resource setup.
- Results: empirical findings and concise interpretation.
- Limitations: scope and unavailable evidence.
- Discussion: implications for performance-evaluation practice.
- Conclusion: brief synthesis, not a second abstract.

