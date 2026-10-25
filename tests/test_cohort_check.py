"""cohort_check：最重要的性质是「样本不够时不许说没退步」。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cohort_check as cc  # noqa: E402

NL = chr(10)


def _run(base, name, completion, cohort="tutorial"):
    d = base / name
    d.mkdir(parents=True)
    rows = [
        {"type": "topic.pick", "at": "2026-10-01T20:00:00+08:00", "cohort": cohort,
         "options": [{"title": "a"}, {"title": "b"}], "chosen": 0},
        {"type": "publish", "at": "2026-10-01T20:30:00+08:00", "bvid": "BV" + name[-2:]},
        {"type": "metrics", "at_hours": 24, "views": 1000, "ctr": 0.05,
         "avg_view_sec": completion * 200, "duration_sec": 200, "likes": 50},
    ]
    (d / "events.jsonl").write_text(NL.join(json.dumps(r, ensure_ascii=False) for r in rows) + NL, encoding="utf-8")


def _batch(base, count, tail=None):
    for i in range(count):
        value = 0.45
        if tail is not None and i >= count - tail[0]:
            value = tail[1]
        _run(base, "run-%02d" % i, value)
    return base


def test_small_sample_never_claims_no_regression(tmp_path):
    root = _batch(tmp_path / "small", 5)
    verdict, notes, mde = cc.judge(cc.collect(root, None))
    assert verdict == "不可判定"
    assert verdict != "没有可判定的退步"
    assert any("样本不足" in n for n in notes)
    assert mde > 0.5


def test_enough_samples_without_a_drop_reports_no_detectable_regression(tmp_path):
    root = _batch(tmp_path / "clean", 40)
    verdict, _, mde = cc.judge(cc.collect(root, None))
    assert verdict == "没有可判定的退步"
    assert mde < 0.4


def test_a_sustained_collapse_is_called_a_regression(tmp_path):
    """检测器换成标定过的 CUSUM 之后，持续性崩塌仍必须被抓到。"""
    root = _batch(tmp_path / "crash", 40, tail=(8, 0.15))
    verdict, notes, _ = cc.judge(cc.collect(root, None))
    assert verdict == "退步"
    assert any("CUSUM" in n for n in notes)


def test_a_three_day_dip_is_not_enough_evidence(tmp_path):
    """3 天的小坑不该报警 —— 旧规则在这里误报，CUSUM 不该。"""
    root = _batch(tmp_path / "dip", 40, tail=(3, 0.30))
    verdict, _, _ = cc.judge(cc.collect(root, None))
    assert verdict != "退步"


def test_min_detectable_shrinks_with_more_samples():
    assert cc.min_detectable(5) > cc.min_detectable(40) > cc.min_detectable(365)
    assert cc.n_needed(0.30) > cc.n_needed(0.60)


def test_empty_input_is_not_a_pass(tmp_path):
    (tmp_path / "empty").mkdir()
    verdict, _, _ = cc.judge(cc.collect(tmp_path / "empty", None))
    assert verdict == "不可判定"


def test_cli_always_prints_the_minimum_detectable_drop(tmp_path, capsys):
    root = _batch(tmp_path / "cli", 5)
    cc.main([str(root), "--cohort", "tutorial", "--window", "5"])
    out = capsys.readouterr().out.strip().splitlines()
    assert out[-1].startswith("本窗口可判定的最小退步")
    assert "不可判定" in "".join(out)