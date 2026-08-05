"""Scorecard math: P&L must be NET of charges — costs are the first adversary."""
import json

from engine import stats


def _fill(ts, side, px, qty, charges, stop=None, conviction=None, tag="test"):
    return json.dumps({"ts": ts, "type": "fill",
                       "order": {"stop": stop, "target": None, "conviction": conviction,
                                 "strategy_tag": tag},
                       "fill": {"symbol": "MM", "side": side, "qty": qty,
                                "price": px, "charges": charges}})


def test_net_of_charges_mm_regression(desk):
    """The real M&M trade: gross +24.09 was reported as a 'win' pre-fix;
    net of Rs32.11 charges it was -8.02."""
    (desk / "journal.jsonl").write_text("\n".join([
        _fill("2026-07-31T15:14:41+05:30", "BUY", 3395.3, 1, 8.03, stop=3295, conviction=65),
        _fill("2026-08-04T11:45:00+05:30", "SELL", 3419.39, 1, 24.08),
    ]) + "\n")
    trades = stats.closed_trades()
    assert len(trades) == 1
    t = trades[0]
    assert t["gross_pnl"] == 24.09
    assert t["charges"] == 32.11
    assert t["pnl"] == -8.02
    assert t["R"] == -0.08  # net R against 100.3 risk

    sc = stats.scorecard()
    assert sc["total_pnl"] == -8.02
    assert sc["win_rate"] == 0.0


def test_fifo_partial_fills(desk):
    (desk / "journal.jsonl").write_text("\n".join([
        _fill("t1", "BUY", 100.0, 10, 5.0, stop=95),
        _fill("t2", "BUY", 110.0, 10, 5.0, stop=105),
        _fill("t3", "SELL", 120.0, 15, 7.5),
    ]) + "\n")
    trades = stats.closed_trades()
    assert len(trades) == 2
    assert trades[0]["qty"] == 10 and trades[0]["entry"] == 100.0
    assert trades[1]["qty"] == 5 and trades[1]["entry"] == 110.0
    # charge proration: lot1 pays 10*0.5 entry + 10*0.5 exit = 10 -> pnl 200-10
    assert trades[0]["pnl"] == 190.0


def test_corrupt_journal_lines_skipped(desk):
    (desk / "journal.jsonl").write_text(
        "not json at all\n" + _fill("t1", "BUY", 100.0, 1, 1.0, stop=95) + "\n")
    assert stats.closed_trades() == []  # open lot, no crash
