"""生命内核：决策是纯函数、状态从日志重算、日志不可篡改。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bili_harness.life import Life, apply, initial_state, policy  # noqa: E402


def test_policy_is_pure():
    state = initial_state()
    obs = {"gaps": 1, "backlog": 9}
    a = policy(state, obs, "2026-10-20T20:00:00+08:00")
    b = policy(json.loads(json.dumps(state)), dict(obs), "2026-10-20T20:00:00+08:00")
    assert a == b
    assert state["tick"] == 0, "policy 不许改动入参"


def test_gap_beats_backlog_and_everything_else():
    assert policy(initial_state(), {"gaps": 2, "backlog": 99}, "t")["action"] == "record_today"
    assert policy(initial_state(), {"gaps": 0, "backlog": 3}, "t")["action"] == "refill_backlog"
    assert policy(initial_state(), {"gaps": 0, "backlog": 9}, "t")["action"] is None


def test_red_line_causes_shutdown_not_retry():
    decision = policy(initial_state(), {"red_line": "自动发布"}, "t")
    assert decision["action"] == "self_shutdown"


def test_state_is_a_pure_function_of_the_log(tmp_path):
    life = Life(tmp_path)
    for i, obs in enumerate([{"gaps": 0, "backlog": 9}, {"gaps": 1, "backlog": 9}, {"gaps": 0, "backlog": 2}]):
        life.tick(obs, "2026-10-%02d" % (20 + i))
    first = life.state
    again = Life(tmp_path).state
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)


def test_tampering_with_the_life_log_is_detected(tmp_path):
    life = Life(tmp_path)
    life.tick({"gaps": 0, "backlog": 9}, "2026-10-20")
    path = tmp_path / "life.jsonl"
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    record["decision"]["action"] = "refill_backlog"
    path.write_text(json.dumps(record, ensure_ascii=False, sort_keys=True) + chr(10), encoding="utf-8")
    with pytest.raises(ValueError):
        Life(tmp_path).replay()


def test_starving_after_seven_idle_days(tmp_path):
    life = Life(tmp_path)
    for i in range(7):
        life.tick({"gaps": 0, "backlog": 99}, "2026-10-%02d" % (20 + i))
    assert life.state["alive"] is False
    assert "饿死" in life.state["death_reason"]


def test_state_at_reconstructs_history(tmp_path):
    life = Life(tmp_path)
    life.tick({"gaps": 1, "backlog": 9}, "2026-10-20")
    life.tick({"gaps": 0, "backlog": 2}, "2026-10-21")
    assert life.state_at(0)["tick"] == 1
    assert life.state_at(1)["tick"] == 2
    assert life.state_at(1)["history"][-1]["action"] == "refill_backlog"


def test_apply_does_not_mutate_input_state():
    state = initial_state()
    apply(state, {"action": "record_today", "reason": "x", "risk": "low"}, {}, "t")
    assert state["tick"] == 0
