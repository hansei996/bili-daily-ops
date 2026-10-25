#!/usr/bin/env python3
"""daily_check —— 把四把闸门串成一张周表 + 一个退出码。

设计依据（FEASIBILITY.md）：不新增第 4 个工具，只把已有的四件（选题准入卡 / 库存水位 /
记录口径 / cohort 对照）串成一条命令。退出码只有三种含义：
    0 = 全部断言通过
    1 = 有硬断言失败（会指到具体日期与落点）
    2 = 输入不合法（目录没有、assert 语法错、周区间写错）—— 不是「看起来还行」

用法:
    python tools/daily_check.py examples/week-2026-10-19 \
        --week 2026-10-19..2026-10-25 \
        --assert "daily>=7" --assert "gate:A1" --assert "meta:title_unique7" \
        --assert "cohort:completion" --assert "stat:n>=5"
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cohort_check as cc  # noqa: E402
import topic_gate  # noqa: E402

BASE_COLUMNS = ("日期", "准入", "发布", "CTR", "cohort", "判定")
METRIC_LABEL = {"completion": "完播", "interaction": "互动", "ctr": "CTR"}


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def parse_week(text):
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})", text or "")
    if not match:
        raise SystemExit(2)
    return match.group(1), match.group(2)


def load_runs(root):
    """读所有 run，返回 [{run, date, title, gate, metrics, cohort}]。"""
    runs = []
    for path in sorted(Path(root).glob("*/events.jsonl")):
        entry = {"run": path.parent.name, "date": None, "title": None, "gate": None, "metrics": None, "cohort": None}
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            etype = event.get("type")
            if etype == "topic.pick":
                chosen = event.get("chosen") or 0
                options = event.get("options") or []
                if options and 0 <= chosen < len(options):
                    entry["title"] = options[chosen].get("title")
                entry["gate"] = event
                entry["cohort"] = event.get("cohort")
            elif etype == "publish":
                entry["date"] = str(event.get("at", ""))[:10]
            elif etype == "metrics":
                entry["metrics"] = event
        if entry["date"]:
            runs.append(entry)
    return runs


def in_week(run, start, end):
    return start <= (run["date"] or "") <= end and run["metrics"] is not None


def build_table(runs, outside=None, metric="completion"):
    rows = []
    values = [cc.ratio(r["metrics"]) for r in runs]
    ref = [cc.ratio(r["metrics"]) for r in (outside or [])]
    pool = [v[metric] for v in ref if v and v.get(metric) is not None]
    if not pool:
        pool = [v[metric] for v in values if v and v.get(metric) is not None]
    median = sorted(pool)[len(pool) // 2] if pool else None
    for run, value in zip(runs, values):
        point = value.get(metric) if value else None
        ctr = value.get("ctr") if value else None
        gate = run["gate"] or {}
        passed = 0
        for rule in ("who", "wrong_now", "can_do_after"):
            if (gate.get("options") or [{}])[0].get(rule) or gate.get(rule):
                passed += 1
        mark = "OK" if (median is None or point is None) else ("低" if point < median * 0.85 else "OK")
        rows.append({
            "日期": run["date"],
            "准入": "%d/3" % passed,
            "发布": "有",
            "指标": "-" if point is None else "%.1f%%" % (point * 100),
            "CTR": "-" if ctr is None else "%.1f%%" % (ctr * 100),
            "cohort": mark,
            "判定": run["run"],
        })
    return rows


def render(rows, metric="completion"):
    columns = ("日期", "准入", "发布", METRIC_LABEL.get(metric, metric), "CTR", "cohort", "判定")
    keys = ["日期", "准入", "发布", "指标", "CTR", "cohort", "判定"]
    widths = [max(len(columns[i]), *(len(str(r[keys[i]])) for r in rows)) if rows else len(columns[i]) for i in range(len(columns))]
    def line(cells):
        return "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells))
    out = [line(columns), line(["-" * w for w in widths])]
    for row in rows:
        out.append(line([row[keys[i]] for i in range(len(columns))]))
    return chr(10).join(out)


def check_asserts(runs, asserts, rows, outside=None, metric="completion"):
    """返回 [(断言, 是否通过, 说明)]。"""
    results = []
    n = len(runs)
    for raw in asserts:
        text = raw.strip()
        if ">=" in text:
            name, value = text.split(">=", 1)
            try:
                target = int(value)
            except ValueError:
                raise SystemExit(2)
            if name == "daily":
                results.append((text, n >= target, "%d 条已发布（要求 >= %d）" % (n, target)))
            elif name.startswith("stat"):
                if name.strip() != "stat:n":
                    raise SystemExit(2)
                results.append((text, n >= target, "%d 条样本（要求 >= %d）" % (n, target)))
            else:
                raise SystemExit(2)
        elif text.startswith("gate:"):
            rule = text.split(":", 1)[1]
            bad = []
            for run in runs:
                gate = run["gate"] or {}
                options = gate.get("options") or []
                chosen = gate.get("chosen") or 0
                payload = options[chosen] if options and chosen < len(options) else {}
                if not payload.get(rule) and not gate.get(rule):
                    bad.append((run["date"], run["run"]))
            results.append((text, not bad, "全部通过" if not bad else
                            "；".join("%s %s 缺 %s" % (d, r, rule) for d, r in bad[:3])))
        elif text == "meta:title_unique7":
            titles = [r["title"] for r in runs if r["title"]]
            dupes = sorted({t for t in titles if titles.count(t) > 1})
            results.append((text, not dupes, "标题不重复" if not dupes else "重复：" + "、".join(dupes)))
        elif text.startswith("cohort:"):
            probe = text.split(":", 1)[1]
            use = metric if probe in ("completion", "interaction", "ctr") else metric
            window_rows = [{"run": r["run"], **cc.ratio(r["metrics"])} for r in runs]
            base_rows = [{"run": r["run"], **cc.ratio(r["metrics"])} for r in (outside or [])]
            verdict, notes, mde = cc.judge(window_rows, metric=use, baseline=base_rows)
            ok = verdict != "退步"
            detail = "%s（本窗口可判定最小退步 %.0f%%）" % (verdict, mde * 100 if mde != float("inf") else 100)
            results.append((text, ok, detail))
        else:
            raise SystemExit(2)
    return results


def main(argv):
    if not argv:
        print("用法：python tools/daily_check.py <runs 目录> --week A..B --assert ...")
        return 2
    root = argv[0]
    if "--week" not in argv:
        print("缺 --week", file=sys.stderr)
        return 2
    start, end = parse_week(argv[argv.index("--week") + 1])
    asserts = [argv[i + 1] for i, a in enumerate(argv) if a == "--assert" and i + 1 < len(argv)]
    if not Path(root).is_dir():
        print("目录不存在：%s" % root, file=sys.stderr)
        return 2

    everything = load_runs(root)
    metric = argv[argv.index("--metric") + 1] if "--metric" in argv else "completion"
    runs = [r for r in everything if in_week(r, start, end)]
    outside = [r for r in everything if not in_week(r, start, end)]
    rows = build_table(runs, outside, metric=metric)
    print(render(rows, metric))
    print()
    if not asserts:
        print("没有断言可跑（退出码 0 只代表输入合法，不代表这周没问题）")
        return 0

    results = check_asserts(runs, asserts, rows, outside, metric=metric)
    for text, ok, detail in results:
        print("%s  %-24s %s" % ("PASS" if ok else "FAIL", text, detail))
    print()
    failed = [t for t, ok, _ in results if not ok]
    if failed:
        print("结果：%d 条断言失败（周区间 %s..%s）" % (len(failed), start, end))
        return 1
    print("结果：%d 条断言全部通过（周区间 %s..%s）" % (len(results), start, end))
    return 0


if __name__ == "__main__":
    _force_utf8()
    sys.exit(main(sys.argv[1:]))