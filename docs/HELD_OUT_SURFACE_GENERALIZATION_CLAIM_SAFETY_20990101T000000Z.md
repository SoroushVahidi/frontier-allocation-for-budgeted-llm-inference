# HELD_OUT_SURFACE_GENERALIZATION_CLAIM_SAFETY_20990101T000000Z

Artifacts: `outputs/held_out_surface_generalization_claim_safety_20990101T000000Z`.

A. Does Strict-F3 remain best on held-out surfaces? not_safe: Strict-F3 is competitive on held-out surfaces, with rank stability evaluated across dataset-budget slices.
B. Does Strict-F3 decisively beat Strict-Gate1-Cap-K6? supportive: Strict-F3 vs Strict-Gate1-Cap-K6 is mixed/fragile unless repeated decisive pairwise wins appear.
C. Do frontier-allocation methods dominate external_l1_max? not_safe: Frontier allocation should be framed as competitive and bounded against external_l1_max.
D. Do held-out results agree with the matched-surface simulation? Mixed agreement; evaluate directionality through pairwise rows.
E. Do held-out results agree with OpenAI+Cohere real-model audits? They are aligned with conservative non-dominance framing.
F. Is the paper safe as a dominance/SOTA paper? not_safe.
G. Is the paper safer as formulation + diagnostic + bounded artifact? safe.
H. What exact table should be added to manuscript/appendix? held_out_claim_safety_table.csv + held_out_surface_pairwise_tests.csv.

Manuscript-safe sentence: Held-out results are mixed and support a conservative formulation-plus-diagnostics framing rather than dominance/SOTA claims.
