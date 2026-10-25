#!/usr/bin/env python3
"""validate_run —— 一条视频的运营记录，必须先过格式这一关。

为什么要有它：复盘最容易变成「感觉这条不如上条」。一旦允许感觉，
指标口径就会一天一个样，回头比什么都比不出来。
所以先把「一条视频长什么样」钉死，再谈判断。

用法:
    python tools/validate_run.py runs/2026-10-25-foo
    python tools/validate_run.py runs/ --all

退出码 0 = 全过；1 = 有问题（会逐条列出规则编号与位置）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RUN_FILE = "events.jsonl"

REQUIRED = {
    "topic.pick": ("options", "chosen"),
    "title.pick": ("candidates", "chosen", "reason"),
    "cover.pick": ("candidates", "chosen", "reason"),
    "publish": ("bvid", "at"),
    # avg_view_sec 是可选的：公开接口不给「平均播放时长」，缺了不许猜，只是算不了完播率
    "metrics": ("at_hours", "views", "duration_sec"),
    "review": ("verdict", "vs", "reason"),
}

VERDICTS = ("better", "worse", "flat")
RATIO_FIELDS = ("ctr", "completion")


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def load(path):
    events = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            events.append((lineno, json.loads(line)))
        except ValueError as exc:
            raise SystemExit("第 %d 行不是合法 JSON：%s" % (lineno, exc))
    return events


def check(events):
    """返回 [(规则号, 行号, 说明)]，空列表表示全过。"""
    problems = []

    def bad(rule, lineno, message):
        problems.append((rule, lineno, message))

    if not events:
        return [("V0", 0, "一份记录都没有：events.jsonl 是空的")]

    seen = {}
    for lineno, event in events:
        etype = event.get("type")
        if etype not in REQUIRED:
            bad("V1", lineno, "未知事件类型 %r（允许：%s）" % (etype, ", ".join(REQUIRED)))
            continue
        seen[etype] = seen.get(etype, 0) + 1
        missing = [name for name in REQUIRED[etype] if name not in event]
        if missing:
            bad("V2", lineno, "%s 缺字段：%s" % (etype, ", ".join(missing)))

        if etype == "metrics":
            views = event.get("views")
            duration = event.get("duration_sec") or 0
            avg = event.get("avg_view_sec")
            if isinstance(views, (int, float)) and views < 0:
                bad("V3", lineno, "views 不能是负数")
            if avg is not None and duration > 0 and avg > duration * 1.02:
                bad("V3", lineno, "avg_view_sec(%.1f) 超过 duration_sec(%.1f)：口径错了（是不是填了总观看时长？）" % (avg, duration))
            for name in RATIO_FIELDS:
                if name in event:
                    value = event[name]
                    if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                        bad("V4", lineno, "%s 必须是 0-1 的比例，收到 %r（不要填百分数）" % (name, value))
            for key, value in event.items():
                if "%" in str(key) or "pct" in str(key).lower():
                    bad("V5", lineno, "字段名 %r 带百分号语义：比例字段请用 0-1，避免两套单位" % (key,))
            if event.get("at_hours") not in (24, 72):
                bad("V6", lineno, "at_hours 只接受 24 或 72（其他时点的平台推荐已大幅衰减，比了也没意义）")

        if etype == "review":
            if event.get("verdict") not in VERDICTS:
                bad("V7", lineno, "verdict 必须是 better/worse/flat，收到 %r" % (event.get("verdict"),))
            if not event.get("vs"):
                bad("V7", lineno, "review 必须写 vs（和哪一条比），否则不可证伪")

        if etype == "topic.pick":
            options = event.get("options") or []
            if len(options) < 2 and not event.get("why_only_one"):
                bad("V8", lineno, "只给了一个选题时必须写 why_only_one：单选项的「选择」不是选择")

    for required_once in ("publish", "metrics"):
        if seen.get(required_once, 0) == 0:
            bad("V9", 0, "缺少 %s 事件：这份记录没法用来复盘" % required_once)
    if seen.get("publish", 0) > 1:
        bad("V9", 0, "publish 出现了 %d 次：一条记录只对应一条视频" % seen["publish"])

    order = [event.get("type") for _, event in events]
    if "publish" in order and "metrics" in order and order.index("publish") > order.index("metrics"):
        bad("V10", 0, "metrics 出现在 publish 之前：先发布才有数据")

    return problems


def main(argv):
    if not argv:
        print("用法：python tools/validate_run.py <run 目录或 runs 目录> [--all]")
        return 1
    root = Path(argv[0])
    if (root / RUN_FILE).exists():
        targets = [root]
    elif root.is_dir():
        targets = sorted(p.parent for p in root.glob("*/" + RUN_FILE))
    else:
        print("找不到 %s" % root)
        return 1

    total_problems = 0
    for run in targets:
        problems = check(load(run / RUN_FILE))
        if problems:
            total_problems += len(problems)
            print("FAIL  %s" % run.name)
            for rule, lineno, message in problems:
                print("   [%s] 第 %s 行  %s" % (rule, lineno or "-", message))
        else:
            print("PASS  %s" % run.name)

    print()
    if total_problems:
        print("结果：%d 条问题，分布在 %d 份记录里" % (total_problems, len(targets)))
        return 1
    print("结果：%d 份记录全部通过" % len(targets))
    return 0


if __name__ == "__main__":
    _force_utf8()
    sys.exit(main(sys.argv[1:]))