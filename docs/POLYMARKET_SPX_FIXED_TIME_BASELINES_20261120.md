# SPX Up/Down — fixed-time settlement baseline research, 2026-11-20

**Status: EXPLORATORY / NO VERIFIED EDGE.** No fills claimed. This historical data was already explored, so none of its late-October rows are a virgin holdout.

## Inputs and provenance

- Private reconstructed YES/NO minute quote archive `H2_Extreme_ES_Research_2026.zip` (SHA256 `d87271f225b4d3b8f6097e9c8ea09e9dda2dbcc9c846d3eac460b1103721ab58`).
- Reference SPX daily price/outcome CSV `recovered/spx_daily.csv` (SHA256 `147ad022b43f5ba0a316afe7871466ab0ee0758a35dc0c44a6ca790fb9c92f63`). **Reference source outcomes have not been independently checked against official Polymarket resolutions.**
- 14:01–14:05 America/New_York, the first eligible snapshot per daily market. YES and NO age <=30 seconds each, quote time skew <=1 second, each spread <= $0.05, both valid bid/ask, no order size proof. 40 eligible/labeled markets (out of 43 original market days). No hindsight-based best entry.
- Buy favorite = side with greater mid-price at fixed time; buy underdog = opposite. Enter at observed **Ask**. Contract payout = 1 USDC if reference SPX outcome matches, else 0. Fee scenario `0.04 * ask * (1 - ask)` per share and purchase, using publicly documented Finance *reference* rate; neither historical contract fee schedule nor actual fills/latency verified. Hold to resolution. No capital cost applied.
- Train = Sep 2026, Validation = Oct 1–15, Reviewed-test = Oct 16–30. This is a **descriptive time split**, not untouched OOS because prior tests have examined this archive.

## Results, per hypothetical 1-share trade

| Side | Train, n=20 | Validation, n=11 | Reviewed test, n=9 | All, n=40 |
|---|---:|---:|---:|---:|
| Buy favorite, mean USDC | **-0.1862** | +0.0754 | +0.0524 | -0.0320 |
| Buy underdog, mean USDC | **+0.1637** | -0.0936 | -0.0706 | +0.0139 |

- Favorite wins 14/20, 11/11 and 9/9 reference resolutions in the three successive periods; the profits depend heavily on the dates and the prices at which shares could be bought.
- Underdog wins 6/20, 0/11 and 0/9. Its apparent profitability on September reverses in October. 40 outcomes is far too small for estimating rare reversals reliably.
- Calculated with one candidate per side per market day, not thousands of minute rows treated as independent trades. Values reported to 4 decimals, as descriptive only.

## Reproduce privately

```bash
python scripts/polymarket_spx_resolution_baselines.py --quotes /path/to/H2_Extreme_ES_Research_2026.zip --reference-spx-daily /path/to/recovered/spx_daily.csv --fee-rate 0.04 --json-out /tmp/spx_resolution_dev_baselines.json
pytest -q backend/tests/test_polymarket_spx_resolution_baselines.py
```

Original private inputs are **not** committed. This script fixes its decision timestamp and comparison rules, has no parameter search, never uses resolution labels to choose the side, and explicitly emits `EXPLORATORY_ONLY_NOT_OOS`. The selected quote is not proof of execution or available order-book size.

## Implications for the next H5 model

Neither buying the side already priced as most likely nor buying the minority side is robust in this tiny cohort. To seek an actual causal edge, acquire verified as-of SPX index spot and previous official close, genuine current-day option bid/ask quote times, and the exact Polymarket event rules/resolution. Then compare a pre-registered close-to-close probability model to observed Polymarket ask+per-market fees, calibrate on earlier days, and require a genuinely future independent OOS sample.
