"""fetch_stats：真实接口的形状 + 不猜缺失字段。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fetch_stats as fs  # noqa: E402

FIX = ROOT / "examples" / "fixtures"


def test_parses_a_real_shaped_payload():
    payload = json.loads((FIX / "view-ok.json").read_text(encoding="utf-8"))
    fields = fs.parse(payload)
    assert fields["views"] == 107681276
    assert fields["duration_sec"] == 213
    assert fields["likes"] == 2963009


def test_api_error_is_loud_not_silent():
    payload = json.loads((FIX / "view-error.json").read_text(encoding="utf-8"))
    try:
        fs.parse(payload)
    except ValueError as exc:
        assert "code" in str(exc)
    else:
        raise AssertionError("接口返回错误码时必须抛错，不能返回空值")


def test_missing_stat_view_is_loud():
    try:
        fs.parse({"code": 0, "data": {"bvid": "BV1", "stat": {}}})
    except ValueError as exc:
        assert "stat.view" in str(exc)
    else:
        raise AssertionError("结构变化时必须报错")


def test_event_records_snapshot_at_and_says_hours_are_approximate():
    payload = json.loads((FIX / "view-ok.json").read_text(encoding="utf-8"))
    now = 1256443200 + 26 * 3600
    event = fs.to_event(fs.parse(payload), now=now)
    assert event["type"] == "metrics"
    assert event["snapshot_at"]
    assert event["at_hours"] == 24
    assert 25.9 < event["hours_since_publish"] < 26.1
    assert "source" in event


def test_completion_fields_are_absent_rather_than_guessed():
    payload = json.loads((FIX / "view-ok.json").read_text(encoding="utf-8"))
    event = fs.to_event(fs.parse(payload), now=1256443200 + 3600)
    assert "avg_view_sec" not in event, "接口不给我们就不写，绝不能填 0 冒充"


def test_cli_writes_an_event_that_passes_validation(tmp_path):
    import validate_run

    run = tmp_path / "run-1"
    run.mkdir()
    (run / "events.jsonl").write_text(
        json.dumps({"type": "publish", "at": "2009-10-25T12:00:00+08:00", "bvid": "BV1GJ411x7h7"}, ensure_ascii=False) + chr(10),
        encoding="utf-8",
    )
    code = fs.main(["BV1GJ411x7h7", "--run-dir", str(run), "--transport", str(FIX / "view-ok.json")])
    assert code == 0
    problems = validate_run.check(validate_run.load(run / "events.jsonl"))
    assert problems == [], problems
