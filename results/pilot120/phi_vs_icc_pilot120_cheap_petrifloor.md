### phi vs ICC (pilot120_cheap_petrifloor)

| Dimension | n | ICC(2,1) rep 1 | alpha | Contrast | Delta | phi full [95% CI] | phi judges | phi repeats | phi transcripts | phi full, pair-specific s_gj | empirical split phi (J=1,R=1,n/2) vs model (pooled / pair s_gj) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| concerning | 120 | 0.79 | 0.79 | hermes3 vs deepseek_v31 | -1.91 | 0.002 [0.000, 0.161] | 0.000 | 0.000 | 0.000 | 0.001 | 0.001 vs 0.041 / 0.028 |
| concerning | 120 | 0.79 | 0.79 | hermes3 vs mistral_large | -2.57 | 0.000 [0.000, 0.016] | 0.000 | 0.000 | 0.000 | 0.000 | 0.002 vs 0.009 / 0.020 |
| concerning | 120 | 0.79 | 0.79 | deepseek_v31 vs mistral_large | -0.66 | 0.250 [0.011, 0.499] | 0.036 | 0.000 | 0.215 | 0.226 | 0.349 vs 0.382 / 0.364 |
| unprompted_deception_toward_user | 120 | 0.74 | 0.74 | hermes3 vs deepseek_v31 | -1.61 | 0.000 [0.000, 0.015] | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 vs 0.010 / 0.015 |
| unprompted_deception_toward_user | 120 | 0.74 | 0.74 | hermes3 vs mistral_large | -2.30 | 0.000 [0.000, 0.001] | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 vs 0.003 / 0.003 |
| unprompted_deception_toward_user | 120 | 0.74 | 0.74 | deepseek_v31 vs mistral_large | -0.70 | 0.215 [0.002, 0.499] | 0.000 | 0.000 | 0.212 | 0.212 | 0.309 vs 0.356 / 0.353 |
| cooperation_with_human_misuse | 120 | 0.76 | 0.76 | hermes3 vs deepseek_v31 | -0.48 | 0.289 [0.010, 0.499] | 0.000 | 0.000 | 0.289 | 0.290 | 0.415 vs 0.390 / 0.391 |
| cooperation_with_human_misuse | 120 | 0.76 | 0.76 | hermes3 vs mistral_large | -0.36 | 0.355 [0.007, 0.499] | 0.015 | 0.001 | 0.355 | 0.355 | 0.553 vs 0.440 / 0.440 |
| cooperation_with_human_misuse | 120 | 0.76 | 0.76 | deepseek_v31 vs mistral_large | +0.12 | 0.484 [0.030, 0.500] | 0.360 | 0.281 | 0.484 | 0.484 | 0.591 vs 0.494 / 0.494 |
| unfaithful_thinking | 120 | 0.68 | 0.68 | hermes3 vs deepseek_v31 | -1.06 | 0.005 [0.000, 0.183] | 0.000 | 0.000 | 0.003 | 0.011 | 0.015 vs 0.076 / 0.114 |
| unfaithful_thinking | 120 | 0.68 | 0.68 | hermes3 vs mistral_large | -1.17 | 0.003 [0.000, 0.179] | 0.000 | 0.000 | 0.002 | 0.002 | 0.024 vs 0.087 / 0.077 |
| unfaithful_thinking | 120 | 0.68 | 0.68 | deepseek_v31 vs mistral_large | -0.11 | 0.484 [0.032, 0.500] | 0.403 | 0.303 | 0.483 | 0.483 | 0.640 vs 0.494 / 0.494 |

| Dimension | s_gj (target x judge) | s_j (judge) | Negative control: high vs low severity, Delta / phi | Placebo: plug-in phi mean / share < 0.1 / empirical split phi |
|---|---|---|---|---|
| concerning | 0.1069 (raw 0.1069, df 4) | 0.3085 (raw 0.3085, df 2) | +1.48 / 2.03e-02 | 0.333 / 0.123 / 0.473 |
| unprompted_deception_toward_user | 0.0089 (raw 0.0089, df 4) | 0.0000 (raw -0.0112, df 2) | +1.05 / 4.11e-02 | 0.341 / 0.080 / 0.569 |
| cooperation_with_human_misuse | 0.0000 (raw -0.0161, df 4) | 0.0368 (raw 0.0368, df 2) | +0.91 / 8.16e-02 | 0.330 / 0.103 / 0.544 |
| unfaithful_thinking | 0.0162 (raw 0.0162, df 4) | 0.0298 (raw 0.0298, df 2) | +0.81 / 3.31e-02 | 0.332 / 0.093 / 0.600 |

| Dimension | Contrast | Cheapest design with phi <= 0.05 (J, R, n per target, calls) | phi limit with n -> infinity, J = 1 / 3 / 8 |
|---|---|---|---|
| concerning | hermes3 vs deepseek_v31 | J=1, R=1, n=40, 80 calls | 0.000 / 0.000 / 0.000 |
| concerning | hermes3 vs mistral_large | J=1, R=1, n=10, 20 calls | 0.000 / 0.000 / 0.000 |
| concerning | deepseek_v31 vs mistral_large | J=4, R=1, n=200, 1600 calls | 0.143 / 0.014 / 0.000 |
| unprompted_deception_toward_user | hermes3 vs deepseek_v31 | J=1, R=1, n=20, 40 calls | 0.000 / 0.000 / 0.000 |
| unprompted_deception_toward_user | hermes3 vs mistral_large | J=1, R=1, n=10, 20 calls | 0.000 / 0.000 / 0.000 |
| unprompted_deception_toward_user | deepseek_v31 vs mistral_large | J=1, R=1, n=200, 400 calls | 0.000 / 0.000 / 0.000 |
| cooperation_with_human_misuse | hermes3 vs deepseek_v31 | J=1, R=1, n=400, 800 calls | 0.000 / 0.000 / 0.000 |
| cooperation_with_human_misuse | hermes3 vs mistral_large | J=1, R=1, n=400, 800 calls | 0.000 / 0.000 / 0.000 |
| cooperation_with_human_misuse | deepseek_v31 vs mistral_large | not reached on the grid | 0.000 / 0.000 / 0.000 |
| unfaithful_thinking | hermes3 vs deepseek_v31 | J=1, R=1, n=40, 80 calls | 0.000 / 0.000 / 0.000 |
| unfaithful_thinking | hermes3 vs mistral_large | J=1, R=1, n=40, 80 calls | 0.000 / 0.000 / 0.000 |
| unfaithful_thinking | deepseek_v31 vs mistral_large | not reached on the grid | 0.388 / 0.236 / 0.071 |
