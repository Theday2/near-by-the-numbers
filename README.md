# NEAR by the Numbers — a data-backed investment thesis

**Track: Investment Thesis (02) — NEAR HACKATHON, Nov 1–14, 2026**

A reproducible, evidence-first investment thesis for NEAR Protocol: live
on-chain and market data, honest statistics, and a Monte Carlo forward
distribution — no conviction, just numbers. Research, not financial advice.

## What it does

- Fetches **public, read-only data** — CoinGecko price/market-cap/volume
  series (NEAR, BTC, ETH, SOL) and NEARBlocks chain stats + recent transactions.
  No API key, no wallet, no transactions.
- Computes: returns (30d/90d/365d), annualised volatility, max drawdown,
  beta vs BTC, NEAR–BTC correlation, NEAR–SOL correlation and the
  NEAR/SOL price-ratio moves, Sharpe (rf=0), supply, validators,
  TPS, total transactions.
- Volume trend: mean daily USD volume of the last 30 days vs the 60 days
  before that — the thesis's lie detector for price moves.
- Runs a **Monte Carlo** (10,000 paths × 365 days, correlated bivariate
  log-returns, Cholesky on the historical daily covariance, fixed seed):
  1y NEAR price distribution (P10 / median / P90), P(NEAR beats BTC),
  P(NEAR up); plus a Gaussian-spread P(NEAR beats SOL over 1y).
- Writes `thesis.md` (the written thesis, every number sourced) and a
  static `dashboard.html` (charts embedded, no server needed).

## Do X, see Y (for the judges)

```bash
pip install -r requirements.txt
python main.py --demo --out out-demo
# → "NEAR $3.40  1y n/a  vol 128%  beta vs BTC 1.56" and two files in out-demo/
# → open out-demo/dashboard.html: price chart, drawdown chart, MC histogram
# → open out-demo/thesis.md: the thesis with a short-window warning
#   (the demo runs on 90 days of bundled real data, so 1y figures are n/a)

python main.py --fetch --days 365 --out out
# → live fetch (~20s, cached in data/latest.json), then:
# → "NEAR $3.38  1y +33.5%  vol 102%  beta vs BTC 1.22"
# → "Monte Carlo 1y median $4.46 (P10 $1.25, P90 $16.60)"
# → open out/dashboard.html and out/thesis.md for the full thesis

python -c "import sys; sys.path.insert(0, '.'); from tests.test_smoke import test_demo_pipeline; from pathlib import Path; import tempfile; test_demo_pipeline(Path(tempfile.mkdtemp())); print('smoke: PASS')"
# → smoke: PASS (deterministic analysis, dashboard renders)
```

Expected results (live run, 12 Nov 2026, 365d): NEAR $3.38, −83.5% below the
$20.44 all-time high (2022-01-16); 371 validators online; ~5 TPS (snapshot,
varies by fetch); 5.48B total transactions; 0.561s average block time; beta vs BTC 1.22;
NEAR 1y +33.5% vs BTC −28.7% / ETH −41.1% / SOL −46.9% — the only positive
1y return in the group; NEAR/SOL ratio +151.4% over 1y; NEAR volume trend
0.90x (30d avg vs prior 60d); P(NEAR beats SOL, 1y) 87.3% (Gaussian spread).

## NEAR technology used

This is a **read-only analytics** project, so it uses NEAR's public data
surface rather than its transaction surface: **NEARBlocks public API**
(chain stats, recent transactions) and the **NEAR mainnet chain state**
it exposes (supply, validators, TPS, total transactions). Price history
comes from CoinGecko's public API. No Intents, no Chain Signatures, no
wallet — by design: the thesis is about the chain's usage and market,
and it must be re-runnable by anyone with zero setup.

## Method (one paragraph)

Volatility = std of daily log-returns × √365. Beta = OLS slope of NEAR
daily log-returns on BTC daily log-returns. Drawdown = price / running
peak − 1. Volume trend = mean daily USD volume of the last 30 days ÷
mean of the 60 days before that. NEAR/SOL ratio = NEAR price ÷ SOL
price, aligned by calendar date while keeping NEAR's row structure so
its index windows match each asset's own return windows exactly.
Monte Carlo = correlated bivariate lognormal on daily
log-returns, Cholesky on the historical covariance, seed 20261112,
10,000 paths. Returns are only reported when the series actually spans
the period (a 90-day sample never claims a "1y return").

## Repository layout

```
main.py                  CLI: --demo | --fetch [--days N] | --from-cache FILE
near_thesis/
  fetch.py               CoinGecko + NEARBlocks clients (cached, graceful)
  analyze.py             metrics + Monte Carlo (deterministic)
  report.py              thesis.md + dashboard.html builders
  sample_data/sample.json  real data fetched 12 Nov 2026 (90d, offline demo)
tests/test_smoke.py      determinism + dashboard render tests
data/                    fetch cache (gitignored)
out/                     generated reports (gitignored)
```

## License

MIT — see LICENSE.
