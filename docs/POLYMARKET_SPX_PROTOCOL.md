# Polymarket SPX Up/Down: evidence-first research protocol v1

**Research question:** Does any pre-registered, causally observable SPX Up/Down strategy earn positive net value after actual Polymarket YES/NO order-book prices, trading fees, latency and realistic fills?

**Isolation:** This repo owns all Polymarket analysis and shadow collection. `Seiltanzer03/trading_dbd` is read-only data provenance, never the target for an experiment commit or production deployment. The standalone shadow collector is opt-in, does not run automatically and does not write any Seiltanzer databases.

## What has been tested

1. H2: buy YES when ES spikes up / buy NO when ES spikes down; first signal per day, 5m exit, realistic Ask in/Bid out. Test P95: -2.4 cents/contract (10 independent daily markets). No robust positive edge; 15m lag variant positive only on seven test days but negative train/validation. Source: user's local `H2_Extreme_ES_Research_2026.zip`, NOT uploaded to this public repo.
2. H4: buy BOTH YES and NO when the two asks sum below $1 (plus fees). 71,415 reconstructed minute snapshots, 43 markets, 0 raw ask combinations below 1.000. Strictly screened eligible pairs: 52,847 across 42 markets, still 0 theoretical discounts. No fill depth proven; never declare true arbitrage even if a future theoretical candidate is detected.
3. SPY 0DTE: 233 historical terminal option models Sep/Oct, 20/43 market days covered, 0 confirmed provider quote timestamps. Recorded BL densities fail forward/moment alignment in most cases. The old `density.q` must not be used as tradable Polymarket fair value.

## Next targeted hypothesis (H5): close-to-close market mispricing

**Contract**: one specified `spx-up-or-down-on-YYYY...` market per NY trading day; official Polymarket event rules are checked per contract. The generic rule uses the official SPX index close vs the previous trading day's close (not the opening price; do not mix with SPX *Opens* markets). Winner must be externally verified, not inferred from a proxy alone.

**At each pre-registered evaluation time**: join Polymarket two-sided YES/NO quotes with (a) verified SPX spot timestamp + previous official close; (b) relevant same-day options, including independently verified option bid/ask and timestamps, OR a strictly past-only realized-vol fallback explicitly labeled as such; (c) fixed 16:00 ET expiry, with early-close/holiday calendar.

**Time causality**: feature quote `available_at <= decision_at`, exact market-day and expiry, per-provider quote timestamps, realistic maximum-age gate and conservative cross-venue lag. Avoid reconstructed future 1m closes and cross-instrument unverified ES/SPX conversions. Existing 233 Yahoo SPY captures remain `TIMING_EXCLUDED`.

**Models**: B0 Polymarket mid quote (a comparator, NOT free tradable execution); B1 frozen past-only physical-up-probability model combining SPX spot distance-to-barrier and realized volatility; B2 option IV only if as-of verified; never equate risk-neutral Q with physical probability P. Freeze family choices on dev; do not tune on test.

**Economics**: choose a position only when predicted edge exceeds executable Ask and the fee at trade time plus a pre-declared slippage/latency buffer. Realized payout at settlement; no simulated arbitrage where both asks are unavailable, no retroactive fills. Correct category- and date-specific Polymarket fee: official public docs give `fee = shares * feeRate * p * (1-p)`, with a current Finance reference coefficient 0.04; verify market-specific fee rate and changes by date rather than applying it blindly to September history. Include time/lockup and order size depth.

**Validation**: independent `market_day` is unit of sample and bootstrap; chronological Train/Validation/Test separated by market day, nested only when truly out of sample. Sep–Oct 2026 was explored and is *development*, no untouched OOS remains there. New prospective paper cohort required. Report trade count, fill coverage, average net cents/contract, cumulative PnL, 95% market-day bootstrap CI, fee sensitivity, control B0, Brier/log loss/calibration, adverse selection, max drawdown and data-missing reasons. Default decision: `NO VERIFIED EDGE` unless all gates pass.

## Secondary experiment (H6, only after H5 data gates)

Passive maker strategies: test limit order fill probability with native L2 order and trade events, queue priority and adverse selection, not just mid-price changes. Require liquidity at actual order time, frozen queue assumptions, maker rebate / fees by market and trade date, matched no-trade baseline. Market making is not proven by a positive quoted spread.

## Public data policy

The original PMData and Databento archives, SPY passive data, and user's private files are **not** committed to this public repository or Pages. Scripts accept private input from a local path or dedicated authorized state; reports contain aggregate metrics only, with hashes and data lineage. No OANDA keys, no live orders, no synthetic/demo data used as empirical evidence.
