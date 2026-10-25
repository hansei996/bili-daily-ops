"""判定快照：同一输入必须给同一结论；输入变了必须明说哪一条变了。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bili_harness import verdict as vd  # noqa: E402


def _runs(values):
    return [
        {"run": "r%d" % i, "date": "2026-10-%02d" % (19 + i), "metrics": {"views": v, "ctr": 0.05}}
        for i, v in enumerate(values)
    ]


def test_snapshot_is_stable_for_the_same_input():
    a = vd.snapshot(_runs([1, 2, 3]), "2026-10-19", "2026-10-25", "completion")
    b = vd.snapshot(_runs([1, 2, 3]), "2026-10-19", "2026-10-25", "completion")
    assert a["digest"] == b["digest"]


def test_snapshot_changes_when_a_metric_changes():
    a = vd.snapshot(_runs([1, 2, 3]), "2026-10-19", "2026-10-25", "completion")
    b = vd.snapshot(_runs([1, 2, 999]), "2026-10-19", "2026-10-25", "completion")
    assert a["digest"] != b["digest"]
    diff = vd.compare({"snapshot": a, "result": {"verdict": "x"}}, b)
    assert diff["same_inputs"] is False
    assert diff["changed_runs"] == ["r2"]


def test_record_then_replay_matches(tmp_path):
    snap = vd.snapshot(_runs([1, 2, 3]), "2026-10-19", "2026-10-25", "completion")
    path = vd.record(tmp_path / "v.json", snap, {"verdict": "ok"})
    entry = vd.load(path)
    assert vd.compare(entry, snap)["same_inputs"] is True


def test_tampered_verdict_file_is_rejected(tmp_path):
    snap = vd.snapshot(_runs([1, 2, 3]), "2026-10-19", "2026-10-25", "completion")
    path = vd.record(tmp_path / "v.json", snap, {"verdict": "ok"})
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["result"]["verdict"] = "全都没问题"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        vd.load(path)


def test_detector_params_are_part_of_the_snapshot():
    """换检测器参数必须让快照哈希变化，否则「同一结论」这句话没有意义。"""
    import hashlib

    snap = vd.snapshot(_runs([1, 2, 3]), "2026-10-19", "2026-10-25", "completion")
    assert snap["detector_params"]["threshold"] == 5.0
    tampered = json.loads(json.dumps(snap))
    tampered["detector_params"]["threshold"] = 4.0
    tampered.pop("digest")
    body = json.dumps(tampered, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(body).hexdigest() != snap["digest"]
