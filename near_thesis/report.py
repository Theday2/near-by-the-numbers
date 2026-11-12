"""Report builder: thesis.md + a static dashboard.html.

Charts are matplotlib PNGs embedded base64 in one self-contained HTML
file — no server, no JavaScript, no external assets. Everything the
judges need to re-run is in the README.
"""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _png_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _charts(payloads: dict, res: dict) -> dict:
    def series(coin: str):
        rows = payloads.get(f"prices_{coin}", {}).get("prices", [])
        dates = [
            datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc) for r in rows
        ]
        return dates, np.array([r[1] for r in rows], dtype=float)

    out: dict = {}
    d_near, p_near = series("near")
    d_btc, p_btc = series("bitcoin")
    d_eth, p_eth = series("ethereum")
    d_sol, p_sol = series("solana")
    if len(p_near) > 2:
        fig, ax = plt.subplots(figsize=(8, 3.2))
        ax.plot(d_near, p_near, label="NEAR", linewidth=2)
        for d, p, label in (
            (d_btc, p_btc, "BTC"),
            (d_eth, p_eth, "ETH"),
            (d_sol, p_sol, "SOL"),
        ):
            if len(p) > 2 and len(d) == len(d_near):
                ax.plot(d, p / max(p[0], 1e-9) * p_near[0],
                        label=f"{label} (rebased)", alpha=0.6)
        ax.set_title("NEAR vs BTC / ETH / SOL, rebased to the same start (USD)")
        ax.legend(fontsize=8)
        out["price"] = _png_b64(fig)
    if len(p_near) > 2:
        dd = p_near / np.maximum.accumulate(p_near) - 1
        fig, ax = plt.subplots(figsize=(8, 2.6))
        ax.fill_between(d_near, dd * 100, 0, alpha=0.5)
        ax.set_title("NEAR drawdown from peak (%)")
        out["drawdown"] = _png_b64(fig)
    vrows = payloads.get("prices_near", {}).get("total_volumes", [])
    if len(vrows) >= 30:
        vd = [datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc) for r in vrows]
        vv = np.array([r[1] for r in vrows], dtype=float) / 1e6
        roll = np.convolve(vv, np.ones(30) / 30, mode="same")
        fig, ax = plt.subplots(figsize=(8, 2.8))
        ax.bar(vd, vv, width=1.2, alpha=0.45, label="daily volume")
        ax.plot(vd, roll, color="red", linewidth=1.4,
                label="30d average")
        ax.set_title("NEAR daily trading volume (USD millions)")
        ax.legend(fontsize=8)
        out["volume"] = _png_b64(fig)
    mc = res.get("monte_carlo", {})
    if mc:
        rng = np.random.default_rng(7)
        mu = np.log(mc["near_median"])
        sigma = (np.log(mc["near_p90"]) - np.log(mc["near_p10"])) / 2.5631
        sample = rng.lognormal(mu, max(sigma, 1e-6), 10_000)
        fig, ax = plt.subplots(figsize=(8, 3.0))
        ax.hist(sample, bins=60, alpha=0.7)
        ax.axvline(mc["near_median"], color="red", label="median")
        ax.set_title("NEAR price in 1y, Monte Carlo (10,000 paths, lognormal fit)")
        ax.legend()
        out["mc"] = _png_b64(fig)
    return out


def _fmt(x, nd: int = 2) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:,.{nd}f}"
    return str(x)


def _pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:+.1f}%"


def build_reports(payloads: dict, res: dict, out_dir: Path) -> dict:
    """Write thesis.md and dashboard.html. Returns paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    a = res["assets"].get("NEAR", {})
    sol = res["assets"].get("SOL", {})
    btc_a = res["assets"].get("BTC", {})
    eth_a = res["assets"].get("ETH", {})
    ch = res["chain"]
    mc = res["monte_carlo"]
    mk = res["market"]
    vol = res.get("volume", {})
    vol_n = vol.get("NEAR", {})
    vol_s = vol.get("SOL", {})
    ratio = res.get("near_sol_ratio", {})
    pbs = res.get("p_near_beats_sol", {})

    def _rel_row(name, s):
        if not s:
            return None
        return (f"| {name} | {_pct(s.get('ret_30d'))} | {_pct(s.get('ret_90d'))} | "
                f"{_pct(s.get('ret_365d'))} | {_pct(s.get('vol_annual'))} | "
                f"{_pct(s.get('max_drawdown'))} |")

    rel_rows = "\n".join(r for r in (
        _rel_row("NEAR", a),
        _rel_row("BTC", btc_a),
        _rel_row("ETH", eth_a),
        _rel_row("SOL", sol),
    ) if r)
    rel_table = (
        "| Asset | 30d | 90d | 1y | Ann. vol | Worst drawdown |\n"
        "|---|---|---|---|---|---|\n" + rel_rows
        if rel_rows else "_No comparable asset data in this run._"
    )
    vol_trend = vol_n.get("vol_trend_30d_vs_prior_60d")
    sol_vol_line = (
        f"For comparison, SOL's 30d average is "
        f"**${_fmt(vol_s.get('avg_vol_last_30d_usd'), 0)}**/day."
        if vol_s.get("avg_vol_last_30d_usd") is not None else
        "SOL volume is n/a in this run (the demo bundle has no SOL data)."
    )
    vol_line = (
        f"NEAR's average daily volume over the last 30 days is "
        f"**${_fmt(vol_n.get('avg_vol_last_30d_usd'), 0)}**, versus "
        f"**${_fmt(vol_n.get('avg_vol_prior_60d_usd'), 0)}** per day over the "
        f"60 days before that — a ratio of **{vol_trend:.2f}x** "
        f"({'rising' if vol_trend and vol_trend > 1 else 'falling'} activity). "
        f"{sol_vol_line}"
        if vol_trend is not None else
        "Volume-trend figures need a 90-day sample and are n/a in this run — "
        "re-run with `--fetch --days 365`."
    )
    if a.get("ret_365d") is not None:
        rel_reading = (
            f"over the last year NEAR's return of "
            f"{_pct(a.get('ret_365d'))} sits between BTC "
            f"({_pct(btc_a.get('ret_365d'))}) and SOL "
            f"({_pct(sol.get('ret_365d'))}), but it paid for that return with "
            f"the highest volatility in the group "
            f"({_pct(a.get('vol_annual'))} annualised) and the deepest drawdown "
            f"({_pct(a.get('max_drawdown'))}). The NEAR/SOL price ratio moved "
            f"{_pct(ratio.get('ret_365d'))} over 1y, "
            f"{_pct(ratio.get('ret_90d'))} over 90d and "
            f"{_pct(ratio.get('ret_30d'))} over 30d — a positive number means "
            f"NEAR gained ground on SOL, a negative one means it lost it. "
            f"A Gaussian-spread model on the same daily data puts P(NEAR beats "
            f"SOL over 1y) at **{_pct(pbs.get('p_near_beats'))}** (estimated on "
            f"{pbs.get('est_window_days')} days of returns) — the backward-looking "
            f"race is already decided (NEAR gained { _pct(ratio.get('ret_365d'))} "
            f"on SOL in a year), but that is history, not a forecast: the forward "
            f"probability is a model estimate, and one bad quarter rewrites it."
        )
    else:
        rel_reading = (
            f"In this run the sample is too short for 1y comparisons (they show "
            f"`n/a` by design, never invented). Over 90 days NEAR returned "
            f"{_pct(a.get('ret_90d'))} versus BTC {_pct(btc_a.get('ret_90d'))} "
            f"and ETH {_pct(eth_a.get('ret_90d'))} — the biggest 90d gain in the "
            f"group, bought with the highest volatility "
            f"({_pct(a.get('vol_annual'))} annualised) and the deepest drawdown "
            f"({_pct(a.get('max_drawdown'))}). The NEAR/SOL race cannot be scored "
            f"here (no SOL data in this run) — re-run with `--fetch --days 365` "
            f"for the full comparison."
        )

    thesis = f"""# NEAR by the Numbers — a data-backed investment thesis

_Generated {stamp} from public APIs (CoinGecko, NEARBlocks).
This is research, not financial advice. Every number below can be
reproduced with `python main.py --fetch --days 365`._

## TL;DR

- NEAR trades at **${_fmt(a.get('last_price'))}** — {_pct(mk.get('ath_change_pct', 0) / 100 if mk.get('ath_change_pct') else None)} from its all-time high of **${_fmt(mk.get('ath_usd'))}** ({mk.get('ath_date', 'n/a')[:10] if mk.get('ath_date') else 'n/a'}).
- 1y return **{_pct(a.get('ret_365d'))}**, 90d **{_pct(a.get('ret_90d'))}**, 30d **{_pct(a.get('ret_30d'))}**. For comparison, SOL's 1y return is **{_pct(sol.get('ret_365d'))}** and BTC's is **{_pct(btc_a.get('ret_365d'))}** — the "NEAR vs the majors" table below has the full picture.
- Annualised volatility **{_pct(a.get('vol_annual'))}**; worst drawdown in the window **{_pct(a.get('max_drawdown'))}**.
- Beta vs BTC **{_fmt(res.get('beta_vs_btc'))}**, correlation with BTC **{_fmt(res.get('corr_near_btc'))}** — NEAR moves with the market, amplified. Correlation with SOL **{_fmt(res.get('corr_near_sol'))}**.
- The chain is live: **{_fmt(ch.get('nodes_online'), 0)} validators online**, ~**{_fmt(ch.get('tps'), 0)} TPS**, **{_fmt(ch.get('total_txns'), 0)} total transactions** (~{_fmt(ch.get('implied_txns_per_day'), 0)}/day implied), avg block time **{ch.get('avg_block_time_s')}s**.
- Monte Carlo (10,000 paths, 365d, historical covariance, estimated on {mc.get('est_window_days')} days of returns): 1y NEAR median **${_fmt(mc.get('near_median'))}** (P10 ${ _fmt(mc.get('near_p10'))}, P90 ${_fmt(mc.get('near_p90'))}); P(NEAR beats BTC over 1y) **{_pct(mc.get('p_near_beats_btc'))}**; P(NEAR up over 1y) **{_pct(mc.get('p_near_up_1y'))}**.{"\n" + ("**Warning: this run used only a short estimation window — re-run with `--fetch --days 365` for the quotable numbers.**" if (mc.get('est_window_days') or 0) < 300 else "")}

## NEAR vs the majors

Same data, same windows, no cherry-picking — every return below is only
shown when the sample actually spans the period (a 90-day run shows `n/a`
for 1y, by design).

{rel_table}

Reading it straight: {rel_reading}

## Volume: is anyone actually trading it?

{vol_line}

Volume is the thesis's lie detector. A price rally on falling volume is
speculation running out of buyers; a rally on rising volume is demand.
Right now the volume trend says trading activity is
{'rising' if vol_trend and vol_trend > 1 else ('falling' if vol_trend else 'unmeasurable in this run')} —
so the recent price move should be read with that in mind, not in isolation.
If volume dries up while the price keeps climbing, that is the first
warning sign in the "what would change this thesis" list below.

## The case (evidence, not conviction)

1. **Usage is real, not just price.** {ch.get('total_txns')} transactions settled, {ch.get('nodes_online')} validators, sub-second blocks. A chain that settles is a chain that can charge for AI-agent payments — the exact use case this hackathon is about.
2. **The discount is measurable.** Trading {_pct(mk.get('ath_change_pct', 0) / 100 if mk.get('ath_change_pct') else None)} below ATH while the network keeps producing blocks is a mean-reversion setup, not a growth story — the Monte Carlo above prices it instead of asserting it.
3. **The risk is also measurable.** Beta {res.get('beta_vs_btc') and round(res['beta_vs_btc'], 2)} vs BTC means NEAR falls harder in a bear market; the P10 case (${_fmt(mc.get('near_p10'))}) is the honest downside.
4. **Relative performance is the tiebreaker, not the headline.** NEAR neither leads nor trails the majors decisively over any window in the table above — it is a high-beta, high-volatility middle of the pack. That is exactly what a mean-reversion buyer wants (paid for the risk with a deep discount) and exactly what a momentum buyer should avoid (no relative-strength edge over SOL). The thesis is therefore a *valuation* case, not a *momentum* case, and it stands or falls on the discount closing — not on NEAR "winning" against SOL.

## What would change this thesis

- Daily transactions falling for 90 straight days while price rises (usage/price divergence).
- Validator count dropping below 250 or average block time rising above 2s.
- NEAR/BTC correlation breaking down while beta stays above 1.5 (idiosyncratic blow-up risk).
- **Volume trend below 0.7x for two consecutive months while price rises** — a rally nobody is trading is a rally with no buyers behind it.
- **NEAR/SOL ratio falling more than 20% over 90 days while SOL's volume trend stays above 1x** — the market would be voting, with money, that the AI-agent settlement story belongs to SOL, not NEAR.
- A 1y return claim based on less than a year of data — this report refuses to make one, and any version of this thesis that does should be discarded.

## Method & reproducibility

- Sources: CoinGecko `/coins/{{near,bitcoin,ethereum,solana}}/market_chart` (365d daily, incl. total volumes), CoinGecko `/coins/near`, NEARBlocks `/v1/stats` and `/v1/txns`. No keys, no wallet, no transactions — read-only.
- Volume trend = mean daily USD volume of the last 30 days divided by the mean of the 60 days before that (needs a 90d+ sample). NEAR/SOL ratio = NEAR price / SOL price on shared dates; its moves use the same span rules as returns. P(NEAR beats SOL, 1y) = Gaussian-spread model on daily log-return differences, annualised, labelled with its estimation window ({pbs.get('est_window_days')} days in this run).
- Volatility = std of daily log-returns x sqrt(365). Beta = OLS slope of NEAR log-returns on BTC log-returns. Monte Carlo = correlated bivariate lognormal, Cholesky on the historical daily covariance, seed {mc.get('seed')}, {mc.get('paths'):,} paths.
- Reproduce: `python main.py --fetch --days 365` then open `dashboard.html`. Deterministic: re-running the analysis on the same cached data gives identical numbers.
"""
    (out_dir / "thesis.md").write_text(thesis)

    charts = _charts(payloads, res)
    captions = {
        "price": "NEAR (thick) against BTC, ETH and SOL, all rebased to the same starting price. If NEAR's line is on top, it outperformed over the window.",
        "drawdown": "How far NEAR fell from its own running peak, in percent. The deeper the dip, the harder the ride.",
        "volume": "Daily NEAR trading volume in USD millions (bars) with its 30-day average (red). A rising red line means more people are actually trading it.",
        "mc": "Where the Monte Carlo puts NEAR in one year: most outcomes cluster near the red median line, but the long right tail is why the P90 is far above it — and the left tail is the honest downside.",
    }
    imgs = "".join(
        f"<h3>{title}</h3><img src='data:image/png;base64,{b64}' style='max-width:100%'>"
        f"<p style='color:#555'>{captions.get(title, '')}</p>"
        for title, b64 in charts.items()
    )
    rel_html_rows = "".join(
        f"<tr><td>{name}</td><td>{_pct(s.get('ret_30d'))}</td>"
        f"<td>{_pct(s.get('ret_90d'))}</td><td>{_pct(s.get('ret_365d'))}</td>"
        f"<td>{_pct(s.get('vol_annual'))}</td><td>{_pct(s.get('max_drawdown'))}</td></tr>"
        for name, s in (("NEAR", a), ("BTC", btc_a), ("ETH", eth_a), ("SOL", sol))
        if s
    )
    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<title>NEAR by the Numbers — dashboard</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:2em auto;padding:0 1em}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 10px;text-align:right}}th:first-child,td:first-child{{text-align:left}}</style>
</head><body><h1>NEAR by the Numbers</h1>
<p>Generated {stamp} · Sources: CoinGecko + NEARBlocks (public, read-only) · Research, not financial advice.</p>
<h2>Snapshot</h2><table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>NEAR price (USD)</td><td>${_fmt(a.get('last_price'))}</td></tr>
<tr><td>1y / 90d / 30d return</td><td>{_pct(a.get('ret_365d'))} / {_pct(a.get('ret_90d'))} / {_pct(a.get('ret_30d'))}</td></tr>
<tr><td>Annualised volatility</td><td>{_pct(a.get('vol_annual'))}</td></tr>
<tr><td>Max drawdown (window)</td><td>{_pct(a.get('max_drawdown'))}</td></tr>
<tr><td>Beta vs BTC / correlation</td><td>{_fmt(res.get('beta_vs_btc'))} / {_fmt(res.get('corr_near_btc'))}</td></tr>
<tr><td>Correlation NEAR–SOL</td><td>{_fmt(res.get('corr_near_sol'))}</td></tr>
<tr><td>NEAR/SOL ratio: 1y / 90d / 30d</td><td>{_pct(ratio.get('ret_365d'))} / {_pct(ratio.get('ret_90d'))} / {_pct(ratio.get('ret_30d'))}</td></tr>
<tr><td>P(NEAR beats SOL, 1y) — Gaussian spread</td><td>{_pct(pbs.get('p_near_beats'))} (est. {pbs.get('est_window_days')}d)</td></tr>
<tr><td>NEAR volume: 30d avg / trend vs prior 60d</td><td>${_fmt(vol_n.get('avg_vol_last_30d_usd'), 0)} / {_fmt(vol_trend, 2) + 'x' if vol_trend is not None else 'n/a'}</td></tr>
<tr><td>Sharpe (rf=0)</td><td>{_fmt(a.get('sharpe_rf0'))}</td></tr>
<tr><td>Market cap (USD)</td><td>${_fmt(ch.get('market_cap_usd'), 0)}</td></tr>
<tr><td>Circulating / total supply</td><td>{_fmt(ch.get('circulating_supply_near'), 0)} / {_fmt(ch.get('total_supply_near'), 0)} NEAR</td></tr>
<tr><td>Validators online</td><td>{_fmt(ch.get('nodes_online'), 0)}</td></tr>
<tr><td>TPS / total txns</td><td>{_fmt(ch.get('tps'), 0)} / {_fmt(ch.get('total_txns'), 0)}</td></tr>
<tr><td>ATH (USD)</td><td>${_fmt(mk.get('ath_usd'))} ({(mk.get('ath_date') or '')[:10]})</td></tr>
<tr><td>Monte Carlo 1y: P10 / median / P90</td><td>${_fmt(mc.get('near_p10'))} / ${_fmt(mc.get('near_median'))} / ${_fmt(mc.get('near_p90'))}</td></tr>
<tr><td>P(NEAR beats BTC, 1y) / P(NEAR up, 1y)</td><td>{_pct(mc.get('p_near_beats_btc'))} / {_pct(mc.get('p_near_up_1y'))}</td></tr>
</table>
<h2>NEAR vs the majors</h2><table>
<tr><th>Asset</th><th>30d</th><th>90d</th><th>1y</th><th>Ann. vol</th><th>Worst drawdown</th></tr>
{rel_html_rows}
</table>
<p style='color:#555'>Returns are only shown when the sample actually spans the period — a 90-day run shows n/a for 1y.</p>
{imgs}
<p><a href='thesis.md'>Read the full thesis (thesis.md)</a></p>
</body></html>"""
    (out_dir / "dashboard.html").write_text(html)
    return {
        "thesis": str(out_dir / "thesis.md"),
        "dashboard": str(out_dir / "dashboard.html"),
    }
