# Polymarket SPX — interactions: SPY Skew RR × ATM IV × Term Slope

**Research date:** 2026-11-20. **Status:** retrospective candidate only — no verified executable edge. This study uses the 20 previously examined market dates in the user's PRIVATE `PM_SPY_All_Option_Metrics_AI_v3.zip` archive; never upload those market/option records to this public repo. No change to the live Seiltanzer terminal.

## Protocol

20 independent NY market days, one fixed daily option snapshot with 10:00–14:00 ET capture, and the first high-quality Polymarket YES/NO quote at least 15 minutes after the option snapshot was **written**. Expanding walk-forward logistic odds correction: first 8 days training, subsequent 12 dates as already-reviewed historical predictions. Every feature mean/scale and model coefficient fit exclusively on earlier independent days. PM YES mid is an offset, not an execution price. Long YES/NO at ASK with a predeclared 3¢ theoretical edge minimum; fee *scenario* 0.04 × Ask × (1−Ask). All fills, per-market 2026 historical fees, SPX event-resolution labels, and option quote-source as-of remain unverified (0 confirmed provider timestamps).

Reproducible code: `scripts/polymarket_spx_option_combinations.py`. Run on private archive locally:

```bash
python scripts/polymarket_spx_option_combinations.py \
  --input-archive /private/PM_SPY_All_Option_Metrics_AI_v3.zip \
  --out-dir /private/polymarket_option_interaction_results
```

The user's full private companion results package `PM_Option_Interactions_20261120_FULL.zip` contains source private archive, predictions, quality-filter replay, charts, pseudo-trades and additional permutation diagnostics. **The package is not published to GitHub.**

## Historical observations, not validated alpha

| Model | Brier (12 reviewed days) | Change vs PM-only calibrated | Scenario net, 1 share/trade |
|---|---:|---:|---:|
| Raw PM YES mid | 0.12223 | −0.00141 | not a trade |
| PM-only calibration | 0.12364 | 0 | 0 |
| Skew RR | 0.09656 | −0.02708 | +0.871, 4 trades |
| ATM IV | 0.09858 | −0.02506 | +1.345, 4 trades |
| Skew + ATM IV | 0.08203 | −0.04161 | +2.029, 7 trades |
| **Skew + ATM IV + Term Slope (three main effects)** | **0.06413** | **−0.05951** | **+2.504, 7 trades** |
| Skew + Term + interaction | 0.07184 | −0.05180 | +0.957, 6 trades |
| Three main + 3 pair interactions | 0.07296 | −0.05067 | +1.409, 7 trades |
| Three main + triple interaction | 0.13394 | **+0.01031** | +1.005, 7 trades |

**No:** increasing complexity did not improve the test by default. The highest-order three-way interaction was worse than the raw market probability.

Best three-main family: seven hypothetical purchases (six successful, one unsuccessful), total +2.5036 USDC *if* every share could be bought at the observed Ask at the historical time and eventual payout matched the reference index close. **66.4% of this retrospective profit came from three trades (Oct 12/15/16) with option-context age 115/1102/1194 minutes.** This does not prove every feature was stale but it makes the inference extremely unreliable.

## Statistical / data-quality adversarial checks

- Two days (Oct 12, Oct 15) explain **60.8%** of the observed 12-day Brier gain; three days explain **80.9%**. Remaining 10 days still show mean improvement ~−0.0280, but historical dates were examined repeatedly.
- Over 12 rolling re-fits the fitted logit adjustment coefficients have consistent signs: skew < 0, ATM IV > 0, term slope < 0. This is retrospective coefficient stability only.
- Paired exact sign-flip p for three-main advantage: ~0.050 before model-selection adjustment. Exploratory 11-model maxT family-wise p ~**0.461**, with no correction for earlier 69 single-metric screens or reused history. **No statistical promotion.**
- Shuffling complete three-feature daily tuples across market days produces a small apparent p (core 0.0025 in 400 shuffles; 11-model search 0.005), but the exchangeability assumption is false or at least questionable with serial time/expiry/regime changes. Such a placebo tests a *different null* and is **not** a trustworthy tradeable-edge significance result.
- Conservative full refit excluding 0DTE and option context age >60min: only **13 total training+testing days; five test days** after eight initial training. Three-main Brier **0.05859** vs raw PM **0.07441** and PM calibrated **0.07738**, two model trades +0.7808 hypothetical USDC. Five dates cannot validate a probability model.
- Changing the fixed ridge penalty 4/8/16/32 gives Brier 0.05135/0.06413/0.08147/0.09675, respectively — magnitude is tuning-sensitive. Do **not** pick the best of these on the same 12 days.

## Candidate to freeze, not to trade

**Primary:** frozen three-main-additive odds correction to Polymarket YES mid. **Secondary:** frozen Skew+ATM IV additive correction. No feature thresholds optimized or third-order products. Test on new future independent SPX market days collected prospectively, with quote timestamps for both option and PM exchanges, an official SPX close threshold and label, 0DTE versus longer-expiry segregation, fees, L2 depth, and no lookahead. Consider ML only after a simple combination demonstrates reproducible net benefit.

Neither these 20 days nor new parameter tweaks on them can count as genuinely unseen OOS.
