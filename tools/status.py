#!/usr/bin/env python3
"""status —— 一句话回答「这个仓现在到底能干什么」。

存在的理由：DECISION-D2 里承认护城河很浅。护城河浅的东西最怕两件事：
夸大（说了做不到）和失忆（做过的又被忘掉）。所以给一条命令，把能力与边界摊平。

用法:
    python tools/status.py
    python tools/status.py --json
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

# (标签, 脚本, 参数, 期望退出码, 输出里必须出现的字样)
# 关键：非零退出常常是**做对了**（拒绝了坏输入），不能一律当成故障。
# 需要临时目录的两条：跑完即清，不污染仓库
# (标签, 用哪个 fixture 播种, 期望退出码, 输出里必须出现的字样)
SEED_CASES = (
    ("真实接口数据能建成合规基线", "examples/fixtures/ranking.json", 0, "已写入"),
    ("风控时报警而不是空跑", "examples/fixtures/ranking-limited.json", 1, "code"),
)

CAN = (
    ("选题准入卡会拒绝烂选题", "tools/topic_gate.py", ["check", "examples/topics.jsonl"], (1,), "打回"),
    ("库存不足时会喊停", "tools/topic_gate.py", ["backlog", "examples/topics.jsonl", "--days", "7"], (1,), "库存不足"),
    ("好记录能通过口径校验", "tools/validate_run.py", ["examples/good"], (0,), "全部通过"),
    ("坏记录会被口径校验抓住", "tools/validate_run.py", ["examples/bad-pct"], (1,), "V4"),
    ("有基线时能判出崩塌", "tools/daily_check.py",
     ["examples/two-weeks", "--week", "2026-10-19..2026-10-25", "--assert", "cohort:completion"], (1,), "退步"),
    ("没基线时不假装判定", "tools/daily_check.py",
     ["examples/week-2026-10-19", "--week", "2026-10-19..2026-10-25", "--assert", "cohort:completion"], (0,), "不可判定"),
)

CANT = (
    "预测哪条会火（只能事后同题材对照，事前就是猜）",
    "判断表达风格好坏（不可清单化）",
    "自动发布 / 登录账号（不做，也不建议做）",
    "拿到精确的 T+24h 快照（接口只给累计值，我们用 snapshot_at 近似并标注）",
    "算出完播率（公开接口不给平均播放时长，缺就留空，不猜）",
)


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def run_case(script, args):
    proc = subprocess.run(
        [sys.executable, str(ROOT / script), *args],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    tail = blob.strip().splitlines()
    return proc.returncode, (tail[-1] if tail else ""), blob


def run_seed(case, tmp_root):
    label, fixture, expected, needle = case
    out = Path(tmp_root) / ("seed-" + str(abs(hash(label))))
    code, tail, blob = run_case("tools/seed_from_ranking.py",
                                ["--top", "3", "--cohort", "selftest", "--out", str(out),
                                 "--transport", fixture])
    ok = code == expected and needle in blob
    return {"能力": label, "命令": "tools/seed_from_ranking.py --transport " + fixture,
            "退出码": code, "期望退出码": [expected], "结果": ok, "最后一行": tail[:80]}


def main(argv):
    rows = []
    for label, script, args, codes, needle in CAN:
        code, tail, blob = run_case(script, args)
        ok = code in codes and needle in blob
        rows.append({"能力": label, "命令": script + " " + " ".join(args), "退出码": code,
                     "期望退出码": list(codes), "结果": ok, "最后一行": tail[:80]})

    import tempfile

    with tempfile.TemporaryDirectory(prefix="bili-status-") as tmp:
        for case in SEED_CASES:
            rows.append(run_seed(case, tmp))

    if "--json" in argv:
        print(json.dumps({"can": rows, "cannot": list(CANT)}, ensure_ascii=False, indent=2))
        return 0 if all(r["结果"] for r in rows) else 1

    print("能做（每条都能一条命令复跑）")
    print("-" * 72)
    for row in rows:
        print("%-32s %s  %s" % (row["能力"][:32], "OK  " if row["结果"] else "FAIL", row["命令"][:60]))
    print()
    print("做不到（写在这里，比写在宣传里有用）")
    print("-" * 72)
    for item in CANT:
        print("  - " + item)
    print()
    passed = sum(1 for r in rows if r["结果"])
    print("结果：%d / %d 项能力自检通过" % (passed, len(rows)))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    _force_utf8()
    sys.exit(main(sys.argv[1:]))