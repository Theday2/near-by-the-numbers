"""Analysis for the NEAR investment thesis.

Everything is computed from the fetched payloads, deterministically
(fixed seed). No prices are invented: every number in the report traces
to a public API response, and every derived number states its formula.

Metrics:
- returns (30d / 90d / 365d), annualised volatility, max drawdown
- beta vs BTC (OLS of NEAR daily log-returns on BTC log-returns),
  correlation, Sharpe ratio (risk-free rate assumed 0, stated)
- price vs all-time high, market cap, supply, implied daily txns
- Monte Carlo forward distribution: 10,000 paths x 365 days of
  correlated bivariate log-returns (NEAR, BTC), Cholesky on the
  historical daily covariance, seed 20261112. Reports the 1y NEAR
  price distribution (P10 / median / P90) and P(NEAR beats BTC).
"""

from __future__ import annotations

import math

import numpy as np

SEED = 20261112
MC_PATHS = 10_000
MC_DAYS = 365


def _prices(payload: dict) -> np.ndarray:
    rows = payload.get("prices", [])
    return np.array([p[1] for p in rows], dtype=float)


def _log_returns(prices: np.ndarray) -> np.ndarray:
    prices = prices[prices > 0]
    return np.diff(np.log(prices))


def _max_drawdown(prices: np.ndarray) -> float:
    peak = np.maximum.accumulate(prices)
    dd = prices / peak - 1.0
    return float(dd.min())


def _beta(near_ret: np.ndarray, btc_ret: np.ndarray) -> float:
    n = min(len(near_ret), len(btc_ret))
    x, y = btc_ret[-n:], near_ret[-n:]
    cov = np.cov(x, y, ddof=1)[0, 1]
    return float(cov / np.var(x, ddof=1))


def _volumes(payload: dict) -> np.ndarray:
    rows = payload.get("total_volumes", [])
    return np.array([v[1] for v in rows], dtype=float)


def _volume_stats(payload: dict, span_days: int) -> dict:
    """Volume trend, honestly windowed.

    - avg_vol_last_30d: mean daily USD volume of the last 30 days.
    - avg_vol_prior_60d: mean daily USD volume of the 60 days before
      that (needs a 90d+ sample).
    - vol_trend_30d_vs_prior_60d: ratio of the two — above 1 means
      trading activity is picking up, below 1 means it is drying up.
    Every figure is None when the sample does not span its window, so
    a 30-day sample can never claim a "90-day volume trend".
    """
    vol = _volumes(payload)
    out = {
        "n_vol_days": int(len(vol)),
        "avg_vol_last_30d_usd": None,
        "avg_vol_prior_60d_usd": None,
        "vol_trend_30d_vs_prior_60d": None,
        "avg_vol_full_usd": None,
    }
    if len(vol) >= 30 and span_days >= 28:
        out["avg_vol_last_30d_usd"] = float(vol[-30:].mean())
    if len(vol) >= 90 and span_days >= 85:
        out["avg_vol_prior_60d_usd"] = float(vol[-90:-30].mean())
        if out["avg_vol_last_30d_usd"] is not None and out["avg_vol_prior_60d_usd"] > 0:
            out["vol_trend_30d_vs_prior_60d"] = float(
                out["avg_vol_last_30d_usd"] / out["avg_vol_prior_60d_usd"]
            )
    if len(vol) >= 1:
        out["avg_vol_full_usd"] = float(vol.mean())
    return out


def _aligned_ratio(near: np.ndarray, other: np.ndarray,
                   near_ts, other_ts) -> tuple[np.ndarray, int]:
    """NEAR/other price ratio, aligned row-for-row with NEAR's series.

    CoinGecko returns one point per day plus a final "now" point, so
    two coins fetched seconds apart have different final timestamps
    and a naive timestamp join drops points and shifts windows. We
    align by UTC calendar date instead — but keep NEAR's row structure
    (today appears twice: the 00:00 close and the "now" point), so the
    ratio's index windows are identical to each asset's own return
    windows and the cross-check
    ratio_90d == (1+NEAR_90d)/(1+SOL_90d)-1 holds exactly.
    Returns (ratio, span_days), where span_days matches the price
    series' own span convention.
    """
    from datetime import datetime, timezone

    def by_date(ts, prices):
        d: dict = {}
        for t, p in zip(ts, prices):
            day = datetime.fromtimestamp(t / 1000, tz=timezone.utc).date()
            d[day] = p  # last point wins if a day repeats
        return d

    dn, do = by_date(near_ts, near), by_date(other_ts, other)
    spine = [datetime.fromtimestamp(t / 1000, tz=timezone.utc).date()
             for t in near_ts]
    common = [day for day in spine if day in dn and day in do]
    if len(common) < 2:
        return np.array([]), 0
    n = np.array([dn[day] for day in common], dtype=float)
    o = np.array([do[day] for day in common], dtype=float)
    o = np.where(o > 0, o, np.nan)
    span = int((near_ts[-1] - near_ts[0]) / 86_400_000) if len(near_ts) >= 2 else 0
    return n / o, span


def _ratio_change(ratio: np.ndarray, span_days: int, days: int, need: int):
    # Same discipline as returns: only claim a move the data spans.
    if len(ratio) > days and span_days >= need and ratio[0] > 0:
        return float(ratio[-1] / ratio[-days - 1] - 1)
    return None


def _p_beats_spread(near_ret: np.ndarray, other_ret: np.ndarray) -> dict:
    """P(NEAR beats the other asset over 1y), Gaussian spread model.

    The daily log-return spread (NEAR − other) is treated as normal
    with its historical mean/vol, annualised over 365 days:
    P = Phi(mu_annual / sigma_annual). This is a model estimate, not
    a Monte Carlo result — it is labelled with its estimation window
    wherever it is shown.
    """
    n = min(len(near_ret), len(other_ret))
    if n < 40:
        return {"p_near_beats": None, "est_window_days": int(n)}
    spread = near_ret[-n:] - other_ret[-n:]
    mu_a = float(spread.mean() * 365)
    sd_a = float(spread.std(ddof=1) * math.sqrt(365))
    if sd_a <= 0:
        return {"p_near_beats": None, "est_window_days": int(n)}
    p = 0.5 * (1.0 + math.erf(mu_a / sd_a / math.sqrt(2)))
    return {"p_near_beats": float(p), "est_window_days": int(n)}


def _series_stats(name: str, prices: np.ndarray, span_days: int) -> dict:
    rets = _log_returns(prices)
    vol = float(np.std(rets, ddof=1) * math.sqrt(365)) if len(rets) > 1 else 0.0

    def _ret(days: int, need: int):
        # Only report a return if the series actually spans that long —
        # a 90d sample must never be labelled a "1y return".
        return (
            float(prices[-1] / prices[-days - 1] - 1)
            if len(prices) > days and span_days >= need
            else None
        )

    out = {
        "n_days": int(len(prices)),
        "span_days": int(span_days),
        "last_price": float(prices[-1]),
        "ret_30d": _ret(30, 28),
        "ret_90d": _ret(90, 85),
        "ret_365d": _ret(365, 360),
        "vol_annual": vol,
        "max_drawdown": _max_drawdown(prices),
        "sharpe_rf0": float(np.mean(rets) / np.std(rets, ddof=1) * math.sqrt(365))
        if len(rets) > 1 and np.std(rets, ddof=1) > 0
        else 0.0,
    }
    return out


def _monte_carlo(near_ret: np.ndarray, btc_ret: np.ndarray, last_near: float,
                 last_btc: float) -> dict:
    n = min(len(near_ret), len(btc_ret))
    x = np.column_stack([near_ret[-n:], btc_ret[-n:]])
    mu = x.mean(axis=0)
    cov = np.cov(x, rowvar=False, ddof=1)
    rng = np.random.default_rng(SEED)
    chol = np.linalg.cholesky(cov)
    shocks = rng.standard_normal((MC_PATHS, MC_DAYS, 2)) @ chol.T + mu
    log_final = shocks.sum(axis=1)
    near_final = last_near * np.exp(log_final[:, 0])
    btc_final = last_btc * np.exp(log_final[:, 1])
    near_growth = near_final / last_near - 1
    btc_growth = btc_final / last_btc - 1
    return {
        "paths": MC_PATHS,
        "horizon_days": MC_DAYS,
        "est_window_days": int(n),
        "seed": SEED,
        "near_p10": float(np.percentile(near_final, 10)),
        "near_median": float(np.percentile(near_final, 50)),
        "near_p90": float(np.percentile(near_final, 90)),
        "near_mean_growth": float(near_growth.mean()),
        "p_near_beats_btc": float((near_growth > btc_growth).mean()),
        "p_near_up_1y": float((near_growth > 0).mean()),
    }


def analyze(payloads: dict) -> dict:
    """Turn raw fetched payloads into the thesis numbers."""
    near = _prices(payloads.get("prices_near", {}))
    btc = _prices(payloads.get("prices_bitcoin", {}))
    eth = _prices(payloads.get("prices_ethereum", {}))
    sol = _prices(payloads.get("prices_solana", {}))
    if len(near) < 40:
        raise ValueError("NEAR price series too short (need 40+ days)")
    out: dict = {"assets": {}}
    keys = {"NEAR": "prices_near", "BTC": "prices_bitcoin",
            "ETH": "prices_ethereum", "SOL": "prices_solana"}
    for name, series in (("NEAR", near), ("BTC", btc), ("ETH", eth),
                         ("SOL", sol)):
        if len(series) >= 40:
            rows = payloads.get(keys[name], {}).get("prices", [])
            span = 0
            if len(rows) >= 2:
                span = int((rows[-1][0] - rows[0][0]) / 86_400_000)
            out["assets"][name] = _series_stats(name, series, span)
    # Volume trends (NEAR + SOL for comparison; BTC/ETH in the payload
    # too, but the thesis only needs the two most relevant).
    out["volume"] = {}
    for name in ("NEAR", "SOL"):
        rows = payloads.get(keys[name], {}).get("total_volumes", [])
        span = 0
        prow = payloads.get(keys[name], {}).get("prices", [])
        if len(prow) >= 2:
            span = int((prow[-1][0] - prow[0][0]) / 86_400_000)
        if len(rows) >= 30:
            out["volume"][name] = _volume_stats(
                payloads.get(keys[name], {}), span)
    near_ret, btc_ret = _log_returns(near), _log_returns(btc)
    out["beta_vs_btc"] = _beta(near_ret, btc_ret)
    n = min(len(near_ret), len(btc_ret))
    out["corr_near_btc"] = float(
        np.corrcoef(near_ret[-n:], btc_ret[-n:])[0, 1]
    )
    # NEAR vs SOL: correlation, relative-price (ratio) moves, and a
    # Gaussian-spread P(NEAR beats SOL over 1y). All span-gated.
    out["corr_near_sol"] = None
    out["near_sol_ratio"] = {"ret_30d": None, "ret_90d": None,
                             "ret_365d": None, "n_days": 0}
    out["p_near_beats_sol"] = {"p_near_beats": None, "est_window_days": 0}
    if len(sol) >= 40:
        sol_ret = _log_returns(sol)
        m = min(len(near_ret), len(sol_ret))
        out["corr_near_sol"] = float(
            np.corrcoef(near_ret[-m:], sol_ret[-m:])[0, 1]
        )
        near_ts = [r[0] for r in payloads.get("prices_near", {}).get("prices", [])]
        sol_ts = [r[0] for r in payloads.get("prices_solana", {}).get("prices", [])]
        ratio, span = _aligned_ratio(near, sol, near_ts, sol_ts)
        out["near_sol_ratio"] = {
            "ret_30d": _ratio_change(ratio, span, 30, 28),
            "ret_90d": _ratio_change(ratio, span, 90, 85),
            "ret_365d": _ratio_change(ratio, span, 365, 360),
            "n_days": int(len(ratio)),
        }
        out["p_near_beats_sol"] = _p_beats_spread(near_ret, sol_ret)
    stats = payloads.get("chain_stats", {}).get("stats", [{}])[0]
    try:
        total_supply = float(stats.get("total_supply", 0)) / 1e24
        circulating = float(stats.get("circulating_supply", 0)) / 1e24
    except (TypeError, ValueError):
        total_supply = circulating = None
    out["chain"] = {
        "total_supply_near": total_supply,
        "circulating_supply_near": circulating,
        "nodes_online": stats.get("nodes_online"),
        "avg_block_time_s": stats.get("avg_block_time"),
        "tps": stats.get("tps"),
        "total_txns": stats.get("total_txns"),
        "implied_txns_per_day": (
            float(stats["tps"]) * 86400 if stats.get("tps") else None
        ),
        "near_price_usd": stats.get("near_price"),
        "market_cap_usd": stats.get("market_cap"),
        "volume_24h_usd": stats.get("volume"),
        "change_24h_pct": stats.get("change_24"),
        "ath_usd": stats.get("high_all"),
    }
    meta = payloads.get("meta_near", {}).get("market_data", {})
    out["market"] = {
        "ath_usd": (meta.get("ath") or {}).get("usd"),
        "ath_change_pct": (meta.get("ath_change_percentage") or {}).get("usd"),
        "ath_date": (meta.get("ath_date") or {}).get("usd"),
        "total_supply": meta.get("total_supply"),
        "circulating_supply": meta.get("circulating_supply"),
        "market_cap_rank": payloads.get("meta_near", {}).get("market_cap_rank"),
    }
    out["monte_carlo"] = _monte_carlo(
        near_ret, btc_ret, float(near[-1]), float(btc[-1])
    )
    return out
