"""rehearse_week：7 天演练必须跑通，且不许把演练数据当真实数据。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _rehearse():
    import os

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "tools/rehearse_week.py"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )


def test_seven_day_rehearsal_passes():
    proc = _rehearse()
    assert proc.returncode == 0, proc.stdout[-1500:] + proc.stderr[-500:]
    out = proc.stdout
    assert "合成数据" in out, "演练必须声明数据是合成的"
    assert "PASS  daily>=7" in out
    assert "合计" in out


def test_rehearsal_labels_its_output_as_synthetic():
    source = (ROOT / "tools" / "rehearse_week.py").read_text(encoding="utf-8")
    assert "rehearsal-synthetic" in source
    assert "rehearsal" in source


def test_unpublished_runs_are_not_invisible_to_the_weekly_table():
    """回归：只有 topic.pick 没有 publish 的记录，周表也必须能看见它。"""
    import subprocess as sp

    code = sp.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'tools'); import daily_check as d; "
         "runs=d.load_runs('examples/week-2026-10-19'); "
         "assert runs, 'load_runs 返回空'; "
         "assert all(r['date'] for r in runs), '有记录没有 date'; print('ok')"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
    )
    assert code.returncode == 0, code.stdout + code.stderr