"""NEAR by the Numbers — a data-backed investment thesis for NEAR.

Usage:
    python main.py --demo            # offline run on bundled sample data
    python main.py --fetch            # live fetch (365d) + analysis + reports
    python main.py --fetch --days 90  # shorter window
    python main.py --from-cache data/latest.json

Outputs (in --out, default ./out/):
    thesis.md       the written investment thesis with every number sourced
    dashboard.html  static dashboard (charts embedded, no server needed)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from near_thesis import analyze, fetch, report  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NEAR by the Numbers")
    ap.add_argument("--demo", action="store_true",
                    help="run on bundled sample data (offline)")
    ap.add_argument("--fetch", action="store_true",
                    help="fetch live data from CoinGecko + NEARBlocks")
    ap.add_argument("--from-cache", type=Path, default=None,
                    help="analyse a cached fetch JSON instead of fetching")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--out", type=Path, default=Path("out"))
    args = ap.parse_args(argv)

    if args.demo:
        print("demo mode: bundled sample data (fetched 12 Nov 2026)")
        payloads = fetch.load_sample()
    elif args.from_cache is not None:
        payloads = json.loads(args.from_cache.read_text())
    elif args.fetch:
        print(f"fetching live data ({args.days}d) ...")
        payloads = fetch.fetch_all(days=args.days,
                                   cache_dir=Path("data"))
    else:
        ap.print_help()
        return 2

    print("analysing ...")
    res = analyze.analyze(payloads)
    paths = report.build_reports(payloads, res, args.out)
    near = res["assets"].get("NEAR", {})
    mc = res["monte_carlo"]

    def _pct1(x):
        return f"{x * 100:+.1f}%" if x is not None else "n/a"

    print(f"NEAR ${near.get('last_price', 0):,.2f}  "
          f"1y {_pct1(near.get('ret_365d'))}  "
          f"vol {near.get('vol_annual', 0) * 100:.0f}%  "
          f"beta vs BTC {res.get('beta_vs_btc', 0):.2f}")
    print(f"Monte Carlo 1y median ${mc['near_median']:,.2f} "
          f"(P10 ${mc['near_p10']:,.2f}, P90 ${mc['near_p90']:,.2f})")
    print(f"wrote {paths['thesis']}")
    print(f"wrote {paths['dashboard']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
