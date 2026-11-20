# Public SPX 0DTE GEX vs Polymarket — exploratory 2026-11-20

**No edge verified.** Source publicly archived delayed CBOE option-chain-derived gamma profile: https://github.com/Alexduanran/spx-0dte-archive/blob/main/gex/summary.csv

- The public source contained 465 GEX records across 40 dates in Sep–Oct 2026. 35 dates had a capture/poll at/before **13:45 New York**.
- Matched the 13:45-or-earlier GEX record to the **first** eligible 14:01–14:05 NY Polymarket YES/NO bid/ask pair for the same day, freshness <=30 seconds, cross-leg quote skew <=1 second, each spread <=5¢. 32 independent days matched; other 3 had no eligible PM quote.
- Source: CBOE public **~15-minute-delayed** chain, sampled by another collector using NY poll time. The actual CBOE option quote timestamps and **GitHub public commit availability at the time of the PM trade are not proven**. This is retrospective historical simulation only. GEX is a model-dependent proxy, not observed dealer hedge inventory.
- Hypothetical **buy PM favorite at Ask and hold** to reference close-to-close outcome, Finance taker fee coefficient 0.04 **scenario only**, not historical per-market fee proof. The independent PM official outcome is not cross-verified, and no PM/option fill is proven.
- Dataset is already explored Sep–Oct 2026; there is **no virgin OOS**.

## Predeclared diagnostic figures

| Explanatory variable (GEX at/before 13:45) | ρ Spearman vs favorite net USDC/share | Approx. unadjusted p |
|---|---:|---:|
| Net same-day GEX | -0.193 | 0.290 |
| GEX sign (positive vs not) | -0.082 | 0.657 |
| Spot distance from gamma flip (bp) | -0.049 | 0.789 |
| Spot distance from max-gamma strike (bp) | +0.126 | 0.493 |

P-values shown are standard asymptotic Spearman p from the initial retrospective diagnostic; the reproducible stdlib script emits permutation p with seed42 and Bonferroni across four tests. None of the four statistics supports a credible association.

Subgroups:
- Negative or zero GEX: 15 days, favorite won 13, hypothetical mean favorite net -0.055 USDC/share.
- Positive GEX: 17 days, favorite won 15, hypothetical mean favorite net -0.055 USDC/share.
- September: 17 days, mean favorite net -0.159 USDC/share.
- October: 15 days, mean favorite net +0.063 USDC/share.

The month sign reversal demonstrates how unstable this historical favorite baseline is. It is not evidence of option GEX strength or an executable hedged option trade. The observed fixed-time PM prices are *not* option bid/ask premiums and cannot price a real multi-leg basket.

## Reproduction, without changing Seiltanzer

```bash
# Download the public GEX source only into private scratch; review its redistribution terms.
curl --fail --location \
  https://raw.githubusercontent.com/Alexduanran/spx-0dte-archive/main/gex/summary.csv \
  --output /private/spx_0dte_public_gex.csv

python scripts/polymarket_public_gex_audit.py \
  --pm-h2-zip /private/H2_Extreme_ES_Research_2026.zip \
  --gex-csv /private/spx_0dte_public_gex.csv \
  --reference-spx-daily /private/spx_daily.csv \
  --output /private/gex_option_signal_diagnostic.json
```

No raw PMData, CBOE/GitHub GEX CSV or SPX reference history is committed or republished to our public Pages. Use signed version and source SHA256 for durable reproduction. Current public GEX archive may gain rows; pin its commit SHA before any future *new* confirmatory experiment.

## What to test next

Prioritize **option prices directly**, i.e., actual time-stamped 0DTE SPXW call/put vertical Bid/Ask around the contract barrier. The selected PM and option legs must settle on equivalent SPX index timestamps (confirm actual SPXW PM settlement style). Research the joint basket realized payoff with costs, integers lots, 100-dollar multiplier and funding margin. Only then test whether option-level relative value explains net PM returns and whether an ML ablation improves a simple baseline.

Candidate data sources with historical 2026 option Bid/Ask and clocks:
- Cboe DataShop option quote intervals: https://datashop.cboe.com/option-quote-intervals
- Databento OPRA historical options: https://databento.com/docs/datasets/opra-pillar
- ThetaData historical option quote data: https://www.thetadata.net/docs/operations/option_history_quote.html

Confirm date coverage, strike depth, licensing, timestamp semantics, 2026 historical availability and price **before paying**. None of these has been purchased or downloaded in this research.
