# Polymarket SPX daily pair parity — independent 2026-11-20 audit

**Decision: HOLD / NO EDGE for buying YES and NO simultaneously at the displayed asks.**

Dataset: supplied H2 research ZIP with `quotes_yes_no_1min_0_21.csv.gz` and `quotes_yes_no_1min_21_43.csv.gz`, reconstructed from separate L2 streams. Dates 2026-09-01 to 2026-10-30; 43 daily SPX Up/Down markets. Source ZIP SHA256: `d87271f225b4d3b8f6097e9c8ea09e9dda2dbcc9c846d3eac460b1103721ab58`. This is private source material; no raw rows are published here.

| Metric | Count / amount |
|---|---:|
| All minute quote pairs | 71,415 |
| Distinct daily SPX markets | 43 |
| Well-formed two-sided pairs (prices 0..1, bid <= ask) | 71,253 |
| Invalid price pairs excluded | 162 |
| Minimum raw YES Ask + NO Ask | **$1.001** |
| Median raw YES Ask + NO Ask | **$1.020** |
| Raw combined Ask below $1 | **0** |
| Eligible pairs: age each <=30s; quote timestamps within 1s; each spread <=$0.05 | 52,847 |
| Markets represented among eligible pairs | 42 |
| Minimum eligible combined Ask | **$1.001** |
| Median eligible combined Ask | **$1.020** |
| Eligible pair with combined Ask below $1 | **0** |

On well-formed pairs not eligible: 11,329 were excluded for excessive spread and 7,077 for quote staleness or future-timestamp validation; filter ordering is deterministic (time first, synchronization second, spread last). For those eligible, there is no fee-free discount, so applying any non-negative fee only makes the candidate worse.

No order book quantities / queue / actual simultaneous fills were proven by this 1-minute quote sample; results are historical snapshots, NOT fills. Earlier or between-minute arbitrage is not ruled out. `min(sum_ask)=1.001` by itself does not imply an executable trade at that price.

## Reproduce on private archive

```bash
python scripts/polymarket_spx_parity_audit.py H2_Extreme_ES_Research_2026.zip --json-out /tmp/polymarket_parity_v1.json
pytest -q backend/tests/test_polymarket_spx_parity_audit.py
```

The parser reads the gzip CSV quote partitions embedded in the provided ZIP. CSV/ZIP files must remain off public GitHub. Default cost buffer is zero to give the arbitrage hypothesis its *best* chance. Fees are not ignored for strategies with positive candidates: fee-aware evaluation is mandatory there. Official fee formula and per-market fee lookup: https://docs.polymarket.com/trading/fees

## Interpretation

This rejects only this **specific** simple buy-both-Ask idea in the captured minute sample. The trading lab's main next task is the pre-registered H5 close-to-close fair-value-vs-Polymarket comparison described in `docs/POLYMARKET_SPX_PROTOCOL.md`, *not* manual threshold overfitting of negative H2 outcomes.
