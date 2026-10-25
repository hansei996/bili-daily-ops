#!/usr/bin/env python3
"""new_run —— 用一条命令开一条视频的记录，别再手写 JSONL。

为什么这个工具比加功能更重要：DECISION-D2 里的第一条关停条件是
「4 周内没人用它记录满 7 天 → 说明记录这个动作太重」。要反驳它，只能把记录做便宜。

行为：
  * 先过选题准入卡（topic_gate.judge），不过就**拒绝创建**（不是警告，是拒绝）；
  * 落 topic.pick（含 cohort），给了 --bvid 就顺带落 publish；
  * 打印下一步的两条命令。

用法:
    python tools/new_run.py --title "3 个把 Claude 用废的坏习惯" --cohort tutorial \
        --who "每天用 AI 写代码但总返工的人" --wrong-now "把 AI 当搜索框一次问一大坨" \
        --can-do-after "用三条自查把返工率降下来" --minutes 20 \
        --metric completion_ratio --baseline 0.38 \
        --weak "同类只讲提示词技巧，不展示返工现场" \
        --counter "问得越详细不一定越好" --date 2026-10-26 [--bvid BV1xx] [--dir runs]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import topic_gate  # noqa: E402


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def slugify(text, limit=24):
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text).strip("-")
    return (text[:limit] or "run").strip("-")


def build_topic(args):
    return {
        "title": args.title,
        "who": args.who,
        "wrong_now": args.wrong_now,
        "can_do_after": args.can_do_after,
        "minutes_to_material": args.minutes,
        "metric": args.metric,
        "metric_baseline": args.baseline,
        "weak_in_existing": args.weak,
        "counter_intuitive": args.counter or [],
    }


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--cohort", default="default")
    parser.add_argument("--who", default="")
    parser.add_argument("--wrong-now", dest="wrong_now", default="")
    parser.add_argument("--can-do-after", dest="can_do_after", default="")
    parser.add_argument("--minutes", type=float, default=None)
    parser.add_argument("--metric", default="")
    parser.add_argument("--baseline", type=float, default=None)
    parser.add_argument("--weak", default="")
    parser.add_argument("--counter", action="append")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--bvid", default=None)
    parser.add_argument("--dir", dest="root", default="runs")
    args = parser.parse_args(argv)

    topic = build_topic(args)
    ok, slot, reasons = topic_gate.judge(dict(topic, title=args.title))
    if not ok:
        print("拒绝创建：这条选题没过准入卡", file=sys.stderr)
        for rule, why in reasons:
            print("  [%s] %s" % (rule, why), file=sys.stderr)
        print()
        print("补全后重来。硬塞进去的记录会让一周的对照失效。", file=sys.stderr)
        return 1

    run_dir = Path(args.root) / ("%s-%s" % (args.date, slugify(args.title)))
    if run_dir.exists():
        print("已存在：%s（换个 --date 或先删掉）" % run_dir, file=sys.stderr)
        return 2
    run_dir.mkdir(parents=True)

    stamp = args.date + "T20:00:00+08:00"
    events = [{
        "type": "topic.pick",
        "at": stamp,
        "cohort": args.cohort,
        "options": [dict(topic, title=args.title), {"title": "（未记录备选）"}],
        "chosen": 0,
        "reason": "由 new_run 记录",
    }]
    if args.bvid:
        events.append({"type": "publish", "at": args.date + "T20:30:00+08:00", "bvid": args.bvid})

    path = run_dir / "events.jsonl"
    path.write_text(chr(10).join(json.dumps(e, ensure_ascii=False) for e in events) + chr(10), encoding="utf-8")

    print("已创建 %s（档位 %s）" % (run_dir, slot))
    print()
    print("下一步：")
    if args.bvid:
        print("  1) 取数   python tools/fetch_stats.py %s --run-dir %s" % (args.bvid, run_dir))
    else:
        print("  1) 发布后补 bvid，再取数：python tools/fetch_stats.py <BVID> --run-dir %s" % run_dir)
    print("  2) 取到数之后再校验  python tools/validate_run.py %s" % run_dir)
    print("  3) 周表   python tools/daily_check.py %s --week %s..%s --assert \"daily>=7\""
          % (args.root, args.date, args.date))
    return 0


if __name__ == "__main__":
    _force_utf8()
    sys.exit(main(sys.argv[1:]))