"""gaps 断言：让「忘记记录」当场可见（D2 关停条件的可观测版本）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import daily_check as dc  # noqa: E402

WEEK = ("2026-10-19", "2026-10-25")


def test_a_full_week_has_no_gap():
    runs = dc.load_runs(ROOT / "examples" / "week-2026-10-19")
    assert dc.longest_gap([r["date"] for r in runs], *WEEK) == 0


def test_a_three_day_hole_is_detected():
    runs = dc.load_runs(ROOT / "examples" / "week-gap")
    assert dc.longest_gap([r["date"] for r in runs], *WEEK) == 3


def test_gap_is_only_counted_inside_the_window():
    """窗口外的空白不能算成断更 —— 这是第一版写错的地方。"""
    runs = dc.load_runs(ROOT / "examples" / "week-2026-10-19")
    dates = [r["date"] for r in runs]
    assert dc.longest_gap(dates, *WEEK) == 0
    # 把窗口放宽到前面 10 天，就应该看到空洞
    assert dc.longest_gap(dates, "2026-10-09", "2026-10-25") >= 8


def test_gaps_assertion_fails_on_the_broken_week():
    runs = dc.load_runs(ROOT / "examples" / "week-gap")
    results = dc.check_asserts(runs, ["gaps:3"], [], window=WEEK)
    assert results[0][1] is False
    assert "连续 3 天" in results[0][2]


def test_gaps_assertion_passes_on_the_full_week():
    runs = dc.load_runs(ROOT / "examples" / "week-2026-10-19")
    results = dc.check_asserts(runs, ["gaps:3"], [], window=WEEK)
    assert results[0][1] is True
