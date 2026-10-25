#!/usr/bin/env python3
"""topic_gate —— 选题准入卡 + 库存水位守门员。

来源：PAIN.md 的结论 —— 日更最容易断在 S0「当天定题」，它是唯一没有降级品的一站。
所以这里做的不是「生成选题」，是**判这条能不能进库**，以及**库还够不够 7 天**。

卡 A（5 条全过才入库，来自 PAIN.md 4.156）：
  1 三行齐：谁遇到 / 现在怎么错 / 看完能立刻做什么
  2 素材可得性：30 分钟内可得 → daily；否则 → weekend
  3 可证伪：成败能用一个具体指标检验
  4 差异化：能指出同类内容的最弱一环
  5 反常识：至少一条反直觉结论

用法:
    python tools/topic_gate.py check topics.jsonl        # 逐条判，列出哪条不过
    python tools/topic_gate.py backlog topics.jsonl --days 7   # 库存水位
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MIN_PER_ITEM = 30  # 分钟：卡 A 第 2 条的硬阈值


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
    items = []
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            items.append(json.loads(line))
        except ValueError as exc:
            raise SystemExit("第 %d 行不是合法 JSON：%s" % (lineno, exc))
    return items


def judge(item):
    """返回 (是否入库, 档位, [(规则, 原因)])。任一规则不过就不入库。"""
    reasons = []

    who = (item.get("who") or "").strip()
    wrong = (item.get("wrong_now") or "").strip()
    act = (item.get("can_do_after") or "").strip()
    if not (who and wrong and act):
        reasons.append(("A1", "三行不齐：who/wrong_now/can_do_after 缺一项就不是选题，只是念头"))

    minutes = item.get("minutes_to_material")
    if not isinstance(minutes, (int, float)):
        reasons.append(("A2", "没写 minutes_to_material：素材多久能拿到必须估，不能含糊"))
        slot = None
    else:
        slot = "daily" if minutes <= MIN_PER_ITEM else "weekend"

    metric = (item.get("metric") or "").strip()
    baseline = item.get("metric_baseline")
    if not metric or baseline in (None, ""):
        reasons.append(("A3", "不可证伪：必须写出 metric 和 metric_baseline（例如 completion_ratio >= 0.38）"))

    if not (item.get("weak_in_existing") or "").strip():
        reasons.append(("A4", "说不出同类内容的最弱一环，就说明我们也不更强"))

    counter = item.get("counter_intuitive") or []
    if not counter or not any(str(x).strip() for x in counter):
        reasons.append(("A5", "没有反直觉结论：只是复述常识，点击率天花板很低"))

    return (not reasons), slot, reasons


def cmd_check(items):
    accepted = 0
    for index, item in enumerate(items, 1):
        ok, slot, reasons = judge(item)
        name = item.get("title") or ("第 %d 条" % index)
        if ok:
            accepted += 1
            print("入库  [%s] %s" % (slot, name))
        else:
            print("打回  %s" % name)
            for rule, why in reasons:
                print("        [%s] %s" % (rule, why))
    print()
    print("结果：%d / %d 条入库" % (accepted, len(items)))
    return 0 if accepted == len(items) else 1


def cmd_backlog(items, days):
    daily = []
    for item in items:
        ok, slot, _ = judge(item)
        if ok and slot == "daily":
            daily.append(item)
    print("日更档库存：%d 条（要求 >= %d）" % (len(daily), days))
    if len(daily) < days:
        missing = days - len(daily)
        print("FAIL  库存不足，缺 %d 条。按 PAIN.md 3.1：今天第一件事是补库，不是拍片。" % missing)
        return 1
    print("PASS  库存够 %d 天，可以按计划推进" % days)
    return 0


def main(argv):
    if len(argv) < 2:
        print("用法：python tools/topic_gate.py <check|backlog> topics.jsonl [--days 7]")
        return 1
    mode, path = argv[0], argv[1]
    days = 7
    if "--days" in argv:
        days = int(argv[argv.index("--days") + 1])
    items = load(path)
    if mode == "check":
        return cmd_check(items)
    if mode == "backlog":
        return cmd_backlog(items, days)
    print("未知模式：%s" % mode)
    return 1


if __name__ == "__main__":
    _force_utf8()
    sys.exit(main(sys.argv[1:]))
