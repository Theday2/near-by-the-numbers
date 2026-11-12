"""Smoke tests: the thesis pipeline runs end-to-end on sample data,
is deterministic, and the dashboard renders."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from near_thesis import analyze, fetch, report  # noqa: E402


def test_demo_pipeline(tmp_path):
    payloads = fetch.load_sample()
    res1 = analyze.analyze(payloads)
    res2 = analyze.analyze(payloads)
    assert json.dumps(res1, sort_keys=True) == json.dumps(res2, sort_keys=True), \
        "analysis must be deterministic"
    paths = report.build_reports(payloads, res1, tmp_path)
    thesis = Path(paths["thesis"]).read_text()
    html = Path(paths["dashboard"]).read_text()
    assert "NEAR" in thesis and "Monte Carlo" in thesis
    assert "data:image/png;base64" in html
    assert res1["assets"]["NEAR"]["last_price"] > 0
    assert 0 <= res1["monte_carlo"]["p_near_beats_btc"] <= 1


def test_cli_demo(tmp_path):
    r = subprocess.run(
        [sys.executable, "main.py", "--demo", "--out", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "thesis.md").exists()
    assert (tmp_path / "dashboard.html").exists()


def test_volume_and_sol_graceful(tmp_path):
    """Volume stats exist on the 90d sample; SOL degrades gracefully;
    a 90d sample must never claim a 1y return (the old bug)."""
    payloads = fetch.load_sample()
    res = analyze.analyze(payloads)
    near = res["assets"]["NEAR"]
    assert near["ret_365d"] is None, "90d sample must not claim a 1y return"
    assert near["ret_90d"] is not None
    assert "SOL" not in res["assets"], "sample has no SOL data"
    vol = res["volume"]["NEAR"]
    assert vol["avg_vol_last_30d_usd"] is not None
    assert vol["avg_vol_prior_60d_usd"] is not None
    assert vol["vol_trend_30d_vs_prior_60d"] is not None
    assert 0 < vol["vol_trend_30d_vs_prior_60d"] < 10
    assert res["near_sol_ratio"]["ret_365d"] is None
    assert res["p_near_beats_sol"]["p_near_beats"] is None
    paths = report.build_reports(payloads, res, tmp_path)
    thesis = Path(paths["thesis"]).read_text()
    html = Path(paths["dashboard"]).read_text()
    assert "Volume" in thesis and "NEAR vs the majors" in thesis
    assert "NEAR volume" in html
    assert "data:image/png;base64" in html
