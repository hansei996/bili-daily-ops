"""status：能力自检本身也要被检查（8 条，全过；且不依赖网络）。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run():
    return subprocess.run(
        [sys.executable, "tools/status.py", "--json"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_status_reports_eight_capabilities_all_passing():
    proc = _run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert len(payload["can"]) == 8
    failed = [row["能力"] for row in payload["can"] if not row["结果"]]
    assert failed == [], "这些能力自检没过：" + ", ".join(failed)


def test_status_states_the_things_it_cannot_do():
    payload = json.loads(_run().stdout)
    joined = "".join(payload["cannot"])
    for must in ("预测哪条会火", "自动发布", "完播率"):
        assert must in joined, "「做不到」清单少了：" + must


def test_status_does_not_need_the_network():
    """全部用例都走 fixture / 本地 examples，断网也必须 8/8。"""
    source = (ROOT / "tools" / "status.py").read_text(encoding="utf-8")
    assert "urllib" not in source, "能力自检不该联网"
    for case in ("ranking.json", "ranking-limited.json"):
        assert case in source
