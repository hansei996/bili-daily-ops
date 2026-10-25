#!/usr/bin/env python3
"""rehearse_week —— 用演练数据把一个真实的一周跑一遍，验证日更流程转得起来。

为什么要有它：DECISION-D2 的第一条关停条件是「记录这个动作太重」。
在真实账号上没有数据之前，唯一能自己验证的是「这条流水线能不能连续跑 7 天、
每步要几条命令、哪一步最烦」。

**它生成的全部是演练数据**，标签写死为 rehearsal，指标是合成值，
不是任何真实视频的播放量。输出里会反复声明这一点。

用法:
    python tools/rehearse_week.py            # 跑一遍并打印每周耗时统计
    python tools/rehearse_week.py --keep     # 保留目录以便人工查看
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def run(args, cwd=None):
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd or ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), time.perf_counter() - started


def make_metrics(run_dir, day_index, views, interaction_pool):
    """写一条演练 metrics —— 数字是合成的，interaction 由池子里的比例决定。"""
    run_dir = Path(run_dir)
    path = run_dir / "events.jsonl"
    likes = int(views * interaction_pool[day_index % len(interaction_pool)])
    event = {
        "type": "metrics",
        "at": "2026-10-%02dT22:00:00+08:00" % (19 + day_index),
        "snapshot_at": "2026-10-%02dT22:00:00+08:00" % (19 + day_index),
        "at_hours": 24,
        "views": views,
        "likes": likes,
        "coins": likes // 3,
        "favorites": likes // 2,
        "replies": likes // 10,
        "shares": likes // 20,
        "duration_sec": 200,
        "source": "rehearsal-synthetic",
        "rehearsal": True,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + chr(10))


def main(argv):
    keep = "--keep" in argv
    workdir = Path(tempfile.mkdtemp(prefix="bili-rehearsal-"))
    runs = workdir / "runs"
    steps = []

    print("演练开始：生成 7 天记录（**全部是合成数据，不是真实播放量**）")
    print()

    start = date(2026, 10, 19)
    for index in range(7):
        day = (start + timedelta(days=index)).isoformat()
        args = [
            str(TOOLS / "new_run.py"),
            "--title", "演练第 %d 天：一个能列三条的坏习惯" % (index + 1),
            "--cohort", "rehearsal",
            "--who", "演练用户",
            "--wrong-now", "现在这么做是错的",
            "--can-do-after", "看完能立刻改",
            "--minutes", "20",
            "--metric", "interaction",
            "--baseline", "0.05",
            "--weak", "同类只讲技巧",
            "--counter", "常识在这里是反的",
            "--date", day,
            "--dir", str(runs),
            "--bvid", "REHEARSAL-" + day,   # 演练用假 bvid：不写 publish 的话这份记录没法完整校验
        ]
        code, out, elapsed = run(args)
        steps.append(("new_run " + day, code, elapsed))
        if code != 0:
            print(out)
            return 1
        run_dir = next(runs.glob(day + "-*"))
        make_metrics(run_dir, index, 1200 + index * 40, [0.052, 0.049, 0.051, 0.050, 0.048, 0.050, 0.047])
        steps.append(("record metrics " + day, 0, 0.0))

    code, out, elapsed = run([str(TOOLS / "validate_run.py"), str(runs)])
    steps.append(("validate 7 份", code, elapsed))
    validate_ok = code == 0

    code, out, elapsed = run([
        str(TOOLS / "daily_check.py"), str(runs),
        "--week", "2026-10-19..2026-10-25",
        "--metric", "interaction",
        "--assert", "daily>=7",
        "--assert", "gate:who",
        "--assert", "meta:title_unique7",
        "--assert", "stat:n>=5",
    ])
    steps.append(("daily_check 一周", code, elapsed))
    weekly_ok = code == 0
    weekly_output = out

    print(weekly_output.strip()[-600:])
    print()
    print("每一步的耗时与命令数")
    print("-" * 56)
    total_seconds = sum(s[2] for s in steps)
    for name, code, elapsed in steps:
        print("  %-28s exit=%d  %.2fs" % (name, code, elapsed))
    print("-" * 56)
    print("合计 %d 步 · %.1f 秒（不含人工取数等待）" % (len(steps), total_seconds))
    print()
    print("结论：一份记录 = 1 条命令 + 1 次取数；一周 7 天 = %d 步。" % len(steps))
    print("      这不是「太重」，但也谈不上轻 —— 真实使用时最大成本是每天记得做，不是操作本身。")

    if keep:
        print()
        print("目录保留在：" + str(workdir))
    else:
        shutil.rmtree(workdir, ignore_errors=True)

    return 0 if (validate_ok and weekly_ok) else 1


if __name__ == "__main__":
    _force_utf8()
    sys.exit(main(sys.argv[1:]))