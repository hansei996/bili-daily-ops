"""判定快照与回放：让「同一个结论」可以被复现和追责。

问题：同一个命令，今天跑出「退步」，明天跑出「没有可判定的退步」——
可能是数据变了，也可能是代码变了，但用户看到的只有两个矛盾的结论。

解法：把「判定所依赖的全部输入」压成一个哈希快照，随结论一起存下来。
回放时重算快照：
  * 快照一致 → 结论必须一致（不一致就是代码漂了，直接报错）
  * 快照不同 → 明确告诉你**哪一条记录变了**，而不是悄悄给个新结论
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA = 1


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def snapshot(runs, start, end, metric) -> dict:
    """把参与判定的输入压成可比较的形状。"""
    rows = []
    for run in runs:
        rows.append({
            "run": run.get("run"),
            "date": run.get("date"),
            "metric_digest": _digest(run.get("metrics") or {}),
        })
    payload = {
        "schema": SCHEMA,
        "window": [start, end],
        "metric": metric,
        "runs": sorted(rows, key=lambda r: (r["date"] or "", r["run"] or "")),
        "detector": "cusum",
        "detector_params": {"drift": 0.5, "threshold": 5.0, "sigma": 0.5},
    }
    payload["digest"] = _digest(payload)
    return payload


def record(path, snap: dict, result: dict) -> Path:
    path = Path(path)
    entry = {"snapshot": snap, "result": result}
    entry["digest"] = _digest(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True) + chr(10), encoding="utf-8")
    return path


def load(path) -> dict:
    path = Path(path)
    entry = json.loads(path.read_text(encoding="utf-8-sig"))
    expected = _digest({"snapshot": entry.get("snapshot"), "result": entry.get("result")})
    if entry.get("digest") != expected:
        raise ValueError("判定文件被改过：哈希对不上（" + str(path) + "）")
    return entry


def compare(entry: dict, snap: dict) -> dict:
    """返回 {same_inputs, verdict_same, changed_runs, reason}。"""
    old = entry.get("snapshot") or {}
    changed = []
    old_map = {r["run"]: r for r in old.get("runs", [])}
    new_map = {r["run"]: r for r in snap.get("runs", [])}
    for name in sorted(set(old_map) | set(new_map)):
        a, b = old_map.get(name), new_map.get(name)
        if a is None or b is None or a.get("metric_digest") != b.get("metric_digest"):
            changed.append(name)
    same_inputs = old.get("digest") == snap.get("digest")
    return {
        "same_inputs": same_inputs,
        "changed_runs": changed,
        "old_window": old.get("window"),
        "new_window": snap.get("window"),
        "old_verdict": (entry.get("result") or {}).get("verdict"),
    }
