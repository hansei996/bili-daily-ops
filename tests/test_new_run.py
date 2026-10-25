"""new_run：记录必须便宜，但便宜不等于放水。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import new_run  # noqa: E402
import validate_run  # noqa: E402

GOOD = [
    "--title", "3 个把 Claude 用废的坏习惯",
    "--cohort", "tutorial",
    "--who", "每天用 AI 写代码但总返工的人",
    "--wrong-now", "把 AI 当搜索框一次问一大坨",
    "--can-do-after", "用三条自查把返工率降下来",
    "--minutes", "20",
    "--metric", "completion_ratio",
    "--baseline", "0.38",
    "--weak", "同类只讲提示词技巧",
    "--counter", "问得越详细不一定越好",
]


def test_good_topic_creates_a_valid_incomplete_run(tmp_path):
    code = new_run.main(GOOD + ["--date", "2026-10-26", "--dir", str(tmp_path / "runs")])
    assert code == 0
    run = next((tmp_path / "runs").iterdir())
    problems = validate_run.check(validate_run.load(run / "events.jsonl"), incomplete=True)
    assert [p for p in problems if p[0].startswith("V")] == [], problems


def test_bad_topic_is_refused_and_nothing_is_created(tmp_path):
    runs = tmp_path / "runs"
    code = new_run.main(["--title", "随便聊聊", "--date", "2026-10-26", "--dir", str(runs)])
    assert code == 1
    assert not runs.exists() or not any(runs.iterdir())


def test_recreating_the_same_day_is_refused(tmp_path):
    runs = tmp_path / "runs"
    assert new_run.main(GOOD + ["--date", "2026-10-26", "--dir", str(runs)]) == 0
    assert new_run.main(GOOD + ["--date", "2026-10-26", "--dir", str(runs)]) == 2


def test_bvid_adds_a_publish_event(tmp_path):
    runs = tmp_path / "runs"
    new_run.main(GOOD + ["--date", "2026-10-26", "--dir", str(runs), "--bvid", "BV1GJ411x7h7"])
    run = next(runs.iterdir())
    types = [json.loads(l)["type"] for l in (run / "events.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert "publish" in types


def test_incomplete_mode_downgrades_missing_metrics_to_a_note(tmp_path):
    runs = tmp_path / "runs"
    new_run.main(GOOD + ["--date", "2026-10-26", "--dir", str(runs)])
    run = next(runs.iterdir())
    strict = validate_run.check(validate_run.load(run / "events.jsonl"))
    lenient = validate_run.check(validate_run.load(run / "events.jsonl"), incomplete=True)
    assert any(p[0] == "V9" for p in strict)
    assert [p for p in lenient if p[0].startswith("V")] == []
