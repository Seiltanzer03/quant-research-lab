# Polymarket SPX probability uplift from SPY IV / skew — retrospective audit

**Date:** 2026-11-20. **Status:** `RESEARCH_ONLY_NO_VERIFIED_EDGE`.

## Objective

Find **positive expected net return** from a calibrated probability difference, not a guaranteed YES+NO arbitrage. Compare two-sided Polymarket market probability with a prior-only statistical correction from SPY option IV and risk-reversal skew. This does NOT claim valid 0DTE risk-neutral digital probabilities or settled option-spread pricing.

## Evidence

Private inputs, not uploaded to this public repository:
- `sp500_spy_sep_oct_2026.zip` — 233 stored SPY proxy option snapshots on 20 NY days. Option fields `option.implied_move.sigma_annual` and `option.skew.rr` are used (not the stale `option_context.option_static`).
- `PM_SPY_Corrected_20_Days_v2/pm_clean_same_day.csv` — 7087 paired same-day, bounded quote-age YES/NO records, spreads <=5¢.
- `recovered/spx_daily.csv` — independent SPX reference labels from index daily closes. Official PM market resolution not independently verified for every day.

**No live Seiltanzer access, code changes, collection, backend cron or trading orders.**

A single event per NY day: first SPY model snapshot in `trades.db` after it was persisted, then first qualifying PM quote **15m or 30m later** (within an additional 6-minute search window). There are 20 matched days. The lag is an anti-lookahead check on storage time, **NOT evidence of genuine option bid/ask time**: 0/233 pass the strict quote-as-of gate. The source selected different expiries, often non-0DTE.

Chronological *historical replay* uses 8 past trading days before the first prediction, subsequently expanding one resolved day at a time. Frozen ridge penalty =8 and fixed minimum theoretical edge 3¢/share, reference fee scenario `0.04 * ask * (1-ask)`; PM purchase at Ask, eventual payout 0/1. Any skew==0 is marked unreliable and excluded from skew training/prediction. These September–October days have been examined before: **not genuinely untouched OOS**.

## Results (independent trading days; lower Brier is better)

| Entry after first option persistence | Model | Evaluated dates | PM market Brier | Model Brier | Model−market | Theoretical trades | Total 1-share USDC after scenario fee |
|---|---|---:|---:|---:|---:|---:|---:|
| 15 min | Market calibration only | 12 | 0.15035 | 0.15402 | +0.00367 | 0 | 0 |
| 15 min | Market + IV | 12 | 0.15035 | **0.18600** | **+0.03566** | 2 | **−0.71769** |
| 15 min | Market + skew only | 6 | 0.08121 | **0.07791** | **−0.00330** | 2 | −0.00438 |
| 15 min | Market + IV + skew | 6 | 0.08121 | 0.09762 | +0.01641 | 2 | −0.51497 |
| 30 min | Market calibration only | 12 | 0.13759 | 0.14071 | +0.00312 | 0 | 0 |
| 30 min | Market + IV | 12 | 0.13759 | **0.16824** | **+0.03064** | 2 | −0.84750 |
| 30 min | Market + skew only | 6 | 0.06824 | **0.06301** | **−0.00523** | 1 | +0.20336 |
| 30 min | Market + IV + skew | 6 | 0.06824 | 0.07606 | +0.00782 | 1 | −0.26770 |

**Critical:** Brier rows with six days are *not comparable* to 12-day rows without restricting to exactly the same dates.

95% per-day bootstrap on model-minus-market score:
- 15min IV, n=12: **[+0.00130, +0.08314]** (deterioration; retrospectively reviewed sample).
- 30min IV, n=12: **[+0.00090, +0.06858]**.
- 15min skew, n=6: **[−0.0203, +0.0150]** (not significant).
- 30min skew, n=6: **[−0.0198, +0.0077]** (not significant).

The two 15-minute IV-model purchases were YES on Oct 16 and Oct 23; both lost. Both were on **0DTE** option dates with unusually high annualized IV. Restricting to the nine days with non-0DTE option expiry, IV's model-minus-market Brier is only **+0.0065** (15min) and **+0.0044** (30min). Mixing expiry regimes distorts naive IV.

Separate first same-expiry option-update experiment (one event per day, n=20, exit after 60m):
- `delta IV` versus next 60m change in YES mid: Spearman **rho ≈ −0.024**, p≈0.920 (exploratory).
- IV-decline versus non-decline split of subsequent PM favorite **Ask-in/Bid-out** return: −7.11¢ (14 days) versus +3.83¢ (6 days), permutation p≈0.208, before fees, not robust. No systematic IV lead proven.

## Interpretation and next source requirement

- Raw IV provided **no incremental probability advantage** in the checked replay; the regime mismatch makes it actively hazardous.
- Skew by itself is a **weak candidate only**, not a confirmed signal. There are only six independently evaluated days, and the trade outcome is dominated by one Oct 23 trade; prospective replication required.
- The source has no true per-contract quote timestamp and no raw historical SPXW call/put Bid/Ask. Therefore cannot verify risk-neutral tail Q, actual hedged option basket payoff or a 5-minute options-lead signal.
- SP500 stored spot comes from a CFD proxy, not exact official intraday SPX. Do not insert it into a digital probability against the official prior close without basis alignment.
- Exact historical Polymarket fee and realized fills are unverified; fee coefficient and 3¢ buffer are **scenario assumptions**, not execution proof.
- Next: genuine timestamped SPXW 0DTE bid/ask surrounding yesterday's official SPX close, aligned official SPX spot, PM orderbook, and newly collected *future* independent market-day outcomes. Then test Q as an explanatory factor in a calibrated physical P(Up) and report net EV/OOS.

## Reproduction

```bash
python scripts/polymarket_spx_option_incremental.py \
  --spy-zip /private/sp500_spy_sep_oct_2026.zip \
  --pm-clean-csv /private/PM_SPY_Corrected_20_Days_v2/pm_clean_same_day.csv \
  --reference-spx-daily /private/spx_daily.csv \
  --json-out /private/polymarket_option_incremental_result.json

pytest -q backend/tests/test_polymarket_spx_option_incremental.py
```

The private companion ZIP `PM_Options_Incremental_Research_20261120.zip` supplied to the user has additional all-day plots, exact per-day trajectories, sensitivity analyses and 6 independent local chronology tests. Private raw data must not be committed to public GitHub Pages or Git history.
