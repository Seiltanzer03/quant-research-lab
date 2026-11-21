# November 2026 holdout: SPY option probability correction does not generalize cleanly

**Date:** 2026-11-21. **Status:** exploratory, **not** a true prospective OOS / not an executable edge. No change to live Seiltanzer.

## Previously frozen hypothesis

The research in [PR #6](https://github.com/Seiltanzer03/quant-research-lab/pull/6) found an apparent 12-day retrospective uplift in PM Brier from an additive `Skew RR + ATM IV + Term Slope` log-odds correction. The historical period (29 Sep–28 Oct) had been screened multiple times; maxT family-wise p≈0.46. Two-model candidate list: three-main correction and `Skew+IV`.

## New evidence from a user-supplied **private** verified Yandex backup

`Seiltanzer_SP500_SPY_options_history_verified_backup_2026-11-21.zip`: 968 unique records from Aug12–Nov20, of which 346 are primary full-triplet SP500 option proxy observations; 233 were already studied. **113 additional direct snapshots across 13 November dates**. The other 621 rows are historical derived option contexts **without chain ATM IV**, not extra valid triplets. Original provider option Bid/Ask and quote timestamps missing in every row.

Freeze original ridge penalty L2=8, train solely on the *20* Sep–Oct one-event-per-day observations (with prior PM yes-mid labels), and select the **first November SPY snapshot from 10:00 to 14:00 NY time** for each date. November 20 is excluded: only one early 09:36 snapshot available in backup. November reference close outcomes (12 days Nov04–19) are from [public SPX 1-minute data](https://github.com/Alexduanran/spx-0dte-archive/tree/main/spx-1m), not verified official Polymarket settlement.

Historical feature covariate drift:

| Feature | Training (20 days) mean | Nov (12 days) mean | Nov days beyond all training extremes |
|---|---:|---:|---:|
| ATM IV | 0.1193 | **0.1915** | **9/12**, above max |
| Skew RR | −0.0464 | **−0.0784** | **7/12**, below min |
| Term slope | +0.3611 | +0.1331 | 1/12 |

Frozen fitted coefficients on all 20 pre-Nov observations: `beta0=-0.09193`, `beta_skew=-0.18383`, `beta_atm_iv=+0.28210`, `beta_term=-0.24366` (z-scored on training features).

**Important diagnostic:** both previously picked models adjust PM YES log-odds **up on all 12 November days**, odds multiplier of three-main model **×1.46 to ×12.72**. Independent daily SPX closes show **4 Up and 8 Down**; the positive probability correction thus **necessarily worsens Brier vs unmodified PM probability on those eight Down days**, regardless of the missing PM YES-mid price. It improves Brier direction on the 4 Up days. **Not an outright directional YES prediction**: adding a positive logit shift can leave P(YES) below 0.5 if the market originally priced YES low.

Excluding a single November **stale option context** (Nov 06 at ~1,220 minutes) leaves 11 fresh, non-0DTE selected snapshots: **8/11 changes still push probability toward the eventual loser**. With 19 or 20 earlier training days and L2 = 4,8,16,32, 12/12 November odds tilts remain positive. This is a retrospective *distribution shift diagnostic*, not a formal alpha test.

**Missing:** archived November PM YES/NO bid/ask quotes at event time, Polymarket official outcome labels, actual 2026 fees and executed fills, and original option quote source timestamps. No valid November Brier **mean** or net PnL has been computed. There is no basis to call the previous +47.5% historical improvement stable. Also 316/346 primary SPY risk-neutral density estimates fail the center-consistency check (95/113 of the November direct snapshots), so no unvalidated density-based digital probability should be used.

## What to obtain next

The user-facing private **`PM_SPY_November_Holdout_20261121_COMPLETE.zip`** includes:
- reproducible offline local script and the original frozen training input, no live-server access;
- `november_day_by_day.csv` (actual features, frozen model shift, realized SPX index close, source freshness);
- `NOVEMBER_PM_QUOTES_TO_FETCH.csv`: **12 exact daily Polymarket slugs**, earliest entry cutoff after first snapshot **database persistence +15min**, six-minute eligibility window, timezone-correct NY timestamps;
- comparative feature-drift tables, figures and full original private input ZIP.

To complete the **actual** Brier/trading test, fetch those 12 markets' historical **both YES and NO bid/ask** pairs with quote ages ≤30s, between-leg skew ≤1s, spread ≤$0.05, official resolutions; use the first eligible pair, not optimal hindsight price. Then compare unchanged odds shifts against each day's PM mid, and hypothetical Ask-in/0-or-1 settlement, strictly marking missing observations as missing. The source is currently not a provable causal option execution feed, so even this follow-up will remain conditional until source quote as-of and fills are verified.

## Reproduce in user's private environment

```sh
python scripts/polymarket_spx_november_holdout.py \
  --option-zip /private/Seiltanzer_SP500_SPY_options_history_verified_backup_2026-11-21.zip \
  --prior-20-csv /private/frozen_daily_input_20.csv \
  --spx-close-csv /private/november_spx_close_reference.csv \
  --out /private/november_holdout_results
```

**No raw private options or PM data in this public repo.** Source file integrity within the supplied backup was asserted by the exporting agent, not independently revalidated from S3/VPS from this analysis environment.
