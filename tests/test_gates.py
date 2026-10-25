"""两把闸门的回归测试：好记录必须过，坏记录必须按规则号被拒。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import topic_gate  # noqa: E402
import validate_run  # noqa: E402

NL = chr(10)

GOOD = [
    {"type": "publish", "at": "2026-10-24T22:30:00+08:00", "bvid": "BV1"},
    {"type": "metrics", "at_hours": 24, "views": 100, "ctr": 0.05, "avg_view_sec": 50, "duration_sec": 200},
]


def _write(tmp_path, name, rows):
    run = tmp_path / name
    run.mkdir()
    body = NL.join(json.dumps(r, ensure_ascii=False) for r in rows) + NL
    (run / "events.jsonl").write_text(body, encoding="utf-8")
    return run


def _rules(run):
    return [p[0] for p in validate_run.check(validate_run.load(run / "events.jsonl"))]


def test_a_well_formed_record_passes(tmp_path):
    run = _write(tmp_path, "ok", GOOD)
    assert validate_run.check(validate_run.load(run / "events.jsonl")) == []


def test_percentage_in_a_ratio_field_is_rejected(tmp_path):
    run = _write(tmp_path, "pct", [GOOD[0], dict(GOOD[1], ctr=5.0)])
    assert "V4" in _rules(run)


def test_avg_view_longer_than_duration_is_rejected(tmp_path):
    run = _write(tmp_path, "long", [GOOD[0], dict(GOOD[1], avg_view_sec=400)])
    assert "V3" in _rules(run)


def test_unfalsifiable_review_is_rejected(tmp_path):
    run = _write(tmp_path, "vague", GOOD + [{"type": "review", "verdict": "感觉还行", "reason": "没写和谁比"}])
    assert "V7" in _rules(run)


def test_metrics_before_publish_is_rejected(tmp_path):
    run = _write(tmp_path, "order", [GOOD[1], GOOD[0]])
    assert "V10" in _rules(run)


def _topic(**kw):
    base = {
        "title": "t", "who": "w", "wrong_now": "n", "can_do_after": "c",
        "minutes_to_material": 10, "metric": "completion_ratio", "metric_baseline": 0.38,
        "weak_in_existing": "x", "counter_intuitive": ["y"],
    }
    base.update(kw)
    return base


def test_good_topic_is_accepted_as_daily():
    ok, slot, reasons = topic_gate.judge(_topic())
    assert ok and slot == "daily" and reasons == []


def test_slow_material_becomes_weekend_slot():
    ok, slot, _ = topic_gate.judge(_topic(minutes_to_material=180))
    assert ok and slot == "weekend"


def test_a_thought_is_not_a_topic():
    ok, _, reasons = topic_gate.judge({"title": "随便聊聊"})
    rules = {r for r, _ in reasons}
    assert not ok
    assert {"A1", "A2", "A3", "A4", "A5"} <= rules


def test_backlog_watermark_fails_when_below_the_line(tmp_path):
    path = tmp_path / "topics.jsonl"
    path.write_text(json.dumps(_topic(), ensure_ascii=False) + NL, encoding="utf-8")
    assert topic_gate.main(["backlog", str(path), "--days", "7"]) == 1
