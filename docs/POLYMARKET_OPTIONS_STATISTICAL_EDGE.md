# Polymarket SPX — statistical edge with options, not risk-free arbitrage

**Research mandate (2026-11-20):** seek a reproducible **positive net expected return** in Polymarket daily SPX Up/Down. A strategy may lose often and still have positive expectancy. The object is *not* to find a guaranteed $1 payout by buying YES+NO. Never claim a statistical edge from price disparity alone.

## Four pre-registered hypothesis families (ordered)

### S1 — Option-implied boundary probability versus prediction market

For each official SPX Up/Down day define the EXACT contractual threshold `K = official prior SPX close`, deadline (official SPX regular close) and event rules. Estimate a *risk-neutral* tail quantity using **same-settlement SPXW call verticals** (best case for minimizing proxy mismatch) or independently verified 0DTE SPY options with marked proxy/cross-asset uncertainty:

`Q(S_T > K) ≈ (C(K-h/2)-C(K+h/2)) / (discount_factor*h)`

This is an approximation only for small strike width `h`; correct for option multiplier, discrete strike availability, matching expiry, put-call parity and actual bid/ask intervals. A call spread approximates a **ramp** around K, not an exact binary digital, and its premium estimates *Q*, **not** physical probability *P*. Require no-static-arbitrage consistency, verified quote as-of and executable quantities.

Compare `Q` to PM YES/NO as an **explanatory signal**, then use calibrated physical `P(Up | features)` and `P - PM Ask - all fees` to predict real net edge. Distinguish systematic risk premia from market mispricing.

### S2 — Real cross-venue **hedged baskets**, not theoretical digital parity

Evaluate *actual* executable multi-leg baskets using synchronized Polymarket orderbook and SPXW option Bid/Ask, fees, sizes and exact settlement times:

- Long PM YES + long put debit spread around official prior close (payout partly offsets an SPX down day).
- Long PM NO + long call debit spread around official prior close.
- Directional PM position + bounded option credit spread for relative value, with realistic risk/margin limits; evaluate only if safe and historically executable.

For one SPXW option vertical, dollar payoff is `100 * min(width, max(...))`, whereas one PM winning share pays $1. Do **not** match one PM share with one option spread. The lot size, option settlement methodology, overlap and basis make the baskets **not risk-free**. Enumerate feasible *integer contract counts* and comparable PM share sizes from **train only**. Evaluate realized joint payoff, trade costs, worst-case loss, CVaR10, capital/margin needed, max drawdown, and daily net PnL. Do not invent historical option bid/ask, price fills or quote timestamps.

### S3 — IV, skew, GEX/OI as **regime-dependent predictors**

Condition PM binary mispricing or its **future returns** on as-of IV term structure, put-call risk reversal, gamma walls, distance from gamma flip, distance to previous official SPX close, remaining trading minutes, and pre-decision ES realized volatility. Freeze units and transformations; avoid combining 2026 historical SPY `density.q` (failed forward check). GEX dealer-sign convention is an estimate, not measured dealer positioning.

Test linear correlations/event-study and *conditional net-return uplift* relative to no-option baseline, with **market-day block bootstrap** and multiple-testing adjustment. Do not treat 233 snapshots as 233 independent days.

### S4 — ES impulse × options state × PM odds response

Extend the previously negative H2 signal with **a pre-declared interaction**, e.g. ES impulse × high-IV or gamma regime versus PM repricing. Never cherry-pick per-day best minute or tune on reviewed October test. Require genuinely new data for final OOS.

## What data are honestly available today

- PM + ES reconstructed Sept/Oct: 43 market days, minute L1 quotes and real ES 1-minute bars in user's PRIVATE local H2 archive.
- SPY: 233 stored model snapshots on 20 NY sessions (Sep 29–Oct 28). Their original bid/ask and independent provider quote timestamps **are absent**; 0 qualify for strict same-day as-of testing. The saved BL density does not pass reliable forward-moment validation. They are NOT option execution prices.
- **Safe diagnostic:** use the *last prior-trading-session stored* skew/ATM IV only, with an SPX daily reference calendar and an at-decision Polymarket 14:01–14:05 ET quote. Earlier capture proves the feature record preceded the next-day decision, but not the current bid/ask quote age. This is a stale, lagged regime feature — not a contemporaneous risk-neutral price.

### Lagged option baseline (retrospective; NOT trading evidence)

Replayed on private H2 quote ZIP, private 233-SPY archive and reference SPX daily outcomes:
- Matched 19 independent NY market days (20 recorded option days, 40 PM quote days at frozen 14:01–14:05 time, some missing previous-day coverage).
- Previous-day put-call risk-reversal skew versus same-day PM YES mid: Spearman rho **-0.054**, descriptive p≈**0.825**.
- Previous-day ATM implied sigma versus PM YES mid: rho **+0.123**, p≈**0.616**.
- Previous-day skew versus favorite-to-expiry hypothetical net return: rho **-0.217**, p≈**0.372**.
- Previous-day ATM implied sigma versus favorite hypothetical net return: rho **+0.041**, p≈**0.867**.
- These p-values are exploratory unadjusted rank-correlation approximations, from only 19 observations; *none* support a signal. PM favorite net return uses a scenario Finance fee rate 0.04, unverified historical market settlements and observed Ask (not actual fills). Multiple-testing correction makes evidence weaker.
- The same-day option distribution cannot be retroactively reconstructed from this data. **No S1/S2 historical net PnL is currently measurable** on these archives.

Reproduction (private inputs only; script outputs aggregate stats, 2-sided permutation p-values and Bonferroni across four fixed tests):

```bash
python scripts/polymarket_lagged_option_audit.py \
  --pm-h2-zip /private/H2_Extreme_ES_Research_2026.zip \
  --spy-zip /private/sp500_spy_sep_oct_2026.zip \
  --reference-spx-daily /private/spx_daily.csv \
  --output /private/lagged_option_diagnostic.json
```

Source SHA256 for audit reproducibility, **no private bytes committed**:
- PM H2 ZIP `d87271f225b4d3b8f6097e9c8ea09e9dda2dbcc9c846d3eac460b1103721ab58`
- SPY ZIP `dc5b5a584d3991191c08138e486b426fe1d1fbfb8b449295904378056225093d`
- reference SPX daily CSV `147ad022b43f5ba0a316afe7871466ab0ee0758a35dc0c44a6ca790fb9c92f63`

## Research acceptance gates

1. **Contract + clocks**: exact PM close-vs-prior-close event and exchange SPX close, option settlement contract, holiday/early close and NY DST; all quotes and features `available_at <= decision_at`.
2. **Independent outcomes and costs**: official resolution or audited close, market-specific fee at historical time, L2 depth/size/slippage, options contract multiplier 100, option commissions and spread Bid/Ask.
3. **Stats**: unaltered day-level samples; development vs chronologically separated validation; future untouched holdout/paper cohort. Estimate mean net return, Brier/log loss, ROI on capital, CVaR10, worst loss, daily bootstrap CI, fee/lag sensitivity, robustness across months/regimes. Price/flow samples within the same day **must not count as independent trials**.
4. **No edge => no ML**. Only after stable, realistic, economically significant uplift, test regularized logistic/gradient boosting against frozen simple model using nested walk-forward and purged groups by day. Report feature ablations, permutation/SHAP with time-safe inputs, probability calibration, and ML incremental profit on **fresh unseen dates**. If apparent gains vanish OOS, reject the enhancement.

**Operational location:** `quant-research-lab` only. Seiltanzer terminal stays read-only; no merge/deploy/worker/API changes in its repository. The Polymarket research has no auto-order execution.

## Supporting reading

- Official daily close-to-close market rules example: https://polymarket.com/event/spx-up-or-down-on-september-3-2026
- Official category-dependent Polymarket fee schedule: https://help.polymarket.com/en/articles/13364478-trading-fees
- Option-implied risk-neutral versus physical distribution evidence: https://onlinelibrary.wiley.com/doi/10.1002/for.3091
- Example recent 0DTE pricing-kernel analysis: https://onlinelibrary.wiley.com/doi/pdf/10.1111/jofi.70070
