"""Data fetchers for the NEAR investment thesis.

All sources are public, read-only, and need no API key and no wallet:
- CoinGecko public API: daily price / market-cap / volume series
  (NEAR, BTC, ETH) + coin metadata.
- NEARBlocks public API: chain snapshot (supply, nodes, TPS, total txns)
  and a sample of recent transactions (proof the chain is live).

Every fetch is cached under ``data/`` so a run is reproducible even if
the network is down; ``--demo`` runs entirely on the bundled sample in
``near_thesis/sample_data/``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

COINGECKO = "https://api.coingecko.com/api/v3"
NEARBLOCKS = "https://api.nearblocks.io/v1"

# CoinGecko's free tier rate-limits aggressively; be polite.
_SLEEP = 2.0


def _get(session: requests.Session, url: str, params: dict | None = None):
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    time.sleep(_SLEEP)
    return resp.json()


def fetch_price_series(session: requests.Session, coin: str, days: int = 365):
    """Daily [timestamp_ms, price_usd] plus market caps and volumes."""
    return _get(
        session,
        f"{COINGECKO}/coins/{coin}/market_chart",
        {"vs_currency": "usd", "days": days, "interval": "daily"},
    )


def fetch_coin_meta(session: requests.Session, coin: str = "near"):
    return _get(
        session,
        f"{COINGECKO}/coins/{coin}",
        {
            "localization": "false",
            "tickers": "false",
            "community_data": "false",
            "developer_data": "false",
        },
    )


def fetch_chain_stats(session: requests.Session):
    """NEARBlocks snapshot: supply, nodes, TPS, total txns, price, mcap."""
    return _get(session, f"{NEARBLOCKS}/stats")


def fetch_recent_txns(session: requests.Session, per_page: int = 5):
    return _get(session, f"{NEARBLOCKS}/txns", {"page": 1, "per_page": per_page})


def fetch_all(days: int = 365, cache_dir: Path | None = None) -> dict:
    """Fetch every source. Returns a dict of raw payloads."""
    session = requests.Session()
    session.headers["User-Agent"] = "near-by-the-numbers/0.1 (hackathon research)"
    out: dict = {}
    for coin in ("near", "bitcoin", "ethereum", "solana"):
        try:
            out[f"prices_{coin}"] = fetch_price_series(session, coin, days)
        except Exception as exc:  # keep going; analysis degrades gracefully
            out[f"prices_{coin}"] = {"error": str(exc)}
    for name, fn in (
        ("meta_near", lambda: fetch_coin_meta(session)),
        ("chain_stats", lambda: fetch_chain_stats(session)),
        ("recent_txns", lambda: fetch_recent_txns(session)),
    ):
        try:
            out[name] = fn()
        except Exception as exc:
            out[name] = {"error": str(exc)}
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        (cache_dir / f"fetch-{stamp}.json").write_text(json.dumps(out, indent=2))
        (cache_dir / "latest.json").write_text(json.dumps(out, indent=2))
    return out


def load_sample() -> dict:
    """Bundled real data (fetched 12 Nov 2026) for offline/demo runs."""
    here = Path(__file__).parent / "sample_data"
    return json.loads((here / "sample.json").read_text())
