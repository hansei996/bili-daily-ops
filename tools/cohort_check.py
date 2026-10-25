#!/usr/bin/env python3
"""cohort_check —— 同题材对照 + 拒绝假绿。

设计依据（ENGINEERING.md，数字都是算过的）：
  * n=7 的 Wilson 95% 下界只有 0.6457 —— 只排除得了 35.4% 的失败率，
    「这周全过 = 没退步」在逻辑上是空句；
  * 90%→70% 的退步要 25 条（3.6 周）才看得见，90%→90%  要 8 条看「崩」；
  * 比值型指标把 sigma(log) 从 0.7 压到 0.3，相当于 5.4 倍等效样本；
  * 并行 A/B 在同一账号不可行（同一推荐池互相挤占），只能做交替/cohort 对照。

所以这个工具的硬规则是：
  **样本不够时输出「不可判定」，绝不允许输出「无退步」。**
  并且最后一行永远打印「本窗口可判定的最小退步」—— 没有这一行就是在假装精确。

用法:
    python tools/cohort_check.py runs/ --cohort tutorial --metric completion --window 7
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

ALPHA_Z = 1.645   # 单侧 0.05
POWER_Z = 0.842   # power 0.80
SIGMA_LOG = 0.5   # 比值型指标的保守估计


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def min_detectable(n, sigma=SIGMA_LOG):
    """n 条能看出的最小相对变化（对数尺度上的一阶近似）。n 越小越大。"""
    if n <= 1:
        return float("inf")
    return (ALPHA_Z + POWER_Z) * sigma * math.sqrt(2.0 / n)


def n_needed(mde, sigma=SIGMA_LOG):
    """要看得出 mde 这么大的相对变化，需要多少条。"""
    if mde <= 0:
        return float("inf")
    return 2.0 * ((ALPHA_Z + POWER_Z) * sigma / mde) ** 2


def ratio(metric_row):
    """把一条 metrics 事件换成比值型指标（避免绝对值跨题材比）。"""
    duration = metric_row.get("duration_sec") or 0
    avg = metric_row.get("avg_view_sec") or 0
    views = metric_row.get("views") or 0
    likes = metric_row.get("likes") or 0
    if duration <= 0:
        return None
    completion = avg / duration
    interaction = (likes / views) if views else 0.0
    return {"completion": completion, "interaction": interaction, "ctr": metric_row.get("ctr")}


def collect(root, cohort=None):
    rows = []
    for path in sorted(Path(root).glob("*/events.jsonl")):
        meta = {}
        metrics = None
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "topic.pick":
                meta["cohort"] = event.get("cohort")
            if event.get("type") == "metrics":
                metrics = event
        if metrics is None:
            continue
        if cohort and meta.get("cohort") != cohort:
            continue
        values = ratio(metrics)
        if values is None:
            continue
        rows.append({"run": path.parent.name, **values})
    return rows


def judge(rows, metric="completion", window=7, target_drop=0.30):
    """返回 (判定, 说明行列表, 最小可判定退步)。判定只允许三种。"""
    values = [r[metric] for r in rows if r.get(metric) is not None]
    n = len(values)
    tail = values[-window:]
    lines = []

    if n == 0:
        return "不可判定", ["没有可用的运行记录"], float("inf")

    mde = min_detectable(n)
    need = n_needed(target_drop)
    median = statistics.median(values)
    lines.append("样本：%d 条（窗口内 %d 条）· 指标 %s · cohort 中位数 %.3f" % (n, len(tail), metric, median))

    if n < need:
        lines.append(
            "要看得出 %.0f%% 的退步需要 %d 条，现在只有 %d 条 —— 样本不足时不判「无退步」。"
            % (target_drop * 100, math.ceil(need), n)
        )
        return "不可判定", lines, mde

    if len(tail) >= 3:
        below = [v for v in tail if v < median * (1 - target_drop / 2)]
        consecutive = 0
        worst = 0
        for value in tail:
            consecutive = consecutive + 1 if value < median * (1 - target_drop / 2) else 0
            worst = max(worst, consecutive)
        if worst >= 3:
            lines.append("连续 %d 条明显低于 cohort 中位数（预注册阈值：连续 3 条）" % worst)
            return "退步", lines, mde
        lines.append("没有连续 3 条低于预注册阈值（当前最长连续 %d 条）" % worst)

    return "没有可判定的退步", lines, mde


def main(argv):
    if not argv:
        print("用法：python tools/cohort_check.py <runs 目录> [--cohort 名称] [--metric completion|interaction|ctr] [--window 7]")
        return 1
    root = argv[0]
    cohort = argv[argv.index("--cohort") + 1] if "--cohort" in argv else None
    metric = argv[argv.index("--metric") + 1] if "--metric" in argv else "completion"
    window = int(argv[argv.index("--window") + 1]) if "--window" in argv else 7

    rows = collect(root, cohort)
    verdict, notes, mde = judge(rows, metric=metric, window=window)
    for row in rows[-window:]:
        value = row.get(metric)
        print("  %-28s %s %.3f" % (row["run"], metric, value if value is not None else float("nan")))
    for note in notes:
        print("  " + note)
    print()
    print("判定：%s" % verdict)
    print("本窗口可判定的最小退步：%.0f%%（n=%d, sigma=%.1f, alpha=0.05 单侧, power=0.80）"
          % (mde * 100, len(rows), SIGMA_LOG))
    return 0 if verdict != "退步" else 2


if __name__ == "__main__":
    _force_utf8()
    sys.exit(main(sys.argv[1:]))
