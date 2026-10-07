# Quantitative Trading & Market Execution Domain — Native Project Domain Skill

## Core Methodology
- Quantitative finance and market execution rules (risk-adjusted residual momentum, zero lookahead bias, vectorized matrix operations, LambdaRank pairwise ranking).
- Alpha modeling: Beta-Stripped Residual Momentum removes systemic benchmark drift and sector bias (especially financial/banking in Nifty 500) to isolate pure idiosyncratic stock alpha:
  $R_{i, t} = \alpha_i + \beta_i R_{m, t} + \epsilon_{i, t}$
  $\text{score}_i = \frac{\sum_{t=T-29}^T \epsilon_{i, t}}{\text{std}(\epsilon_{i, 1..60})}$
- LightGBM LambdaRank: Grouped listwise/pairwise learning to rank on cross-sectional candidates evaluated on NDCG@1 and NDCG@3, targeting top setups with 5-day forward return quantiles.
