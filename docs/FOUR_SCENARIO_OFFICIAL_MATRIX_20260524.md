# FOUR_SCENARIO_OFFICIAL_MATRIX_20260524

Selector matrix across official scenarios (diagnostic replay where applicable).

          selector  cohere_gsm8k  cohere_math500  mistral_gsm8k  mistral_math500  official_macro_mean
oracle_best_action      0.933333        0.450000       0.940000         0.676667             0.750000
oracle_best_source      0.933333        0.450000       0.940000         0.676667             0.750000
          C1a_t005      0.836667        0.293333       0.913333         0.563333             0.651667
               C1d      0.836667        0.293333       0.913333         0.563333             0.651667
    beta_shrinkage      0.836667        0.293333       0.913333         0.563333             0.651667
           pooled4      0.836667        0.293333       0.910000         0.556667             0.649167
         always_S1      0.800000        0.280000       0.913333         0.563333             0.639167
                S1      0.800000        0.280000       0.913333         0.563333             0.639167
    agreement_only      0.823333        0.330000       0.846667         0.536667             0.634167
          frontier      0.790000        0.290000       0.786667         0.400000             0.566667
                L1      0.796667        0.243333       0.726667         0.456667             0.555833
              TALE      0.806667        0.253333       0.670000         0.480000             0.552500

Recommended selector by four-scenario macro (diagnostic): oracle_best_action.

C1d/C1a/FIX-03 here are diagnostic replays when not computed with fold-safe CV on this exact matrix.
