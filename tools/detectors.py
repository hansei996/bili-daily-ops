#!/usr/bin/env python3
"""detectors —— 退步检测的几种算法，以及它们的实测表现。

背景：我之前用的规则是「连续 3 条低于基线阈值」，那个阈值是拍的。
这个文件把它换成可比较的东西：在同一批**已知真值**的合成序列上，
量出每个检测器的「发现延迟」与「误报率」，再决定用哪个。

为什么不用账户数据：检测器好不好是**统计性质**，可以用仿真量出来；
真实数据只用来调参，不适合用来证明方法本身。

方法：
  * rule3     当前规则：连续 3 条低于 中位数*(1-d/2)
  * cusum     双侧 CUSUM（标准化，参考值 k=0.5 sigma，阈值 h 由误报率标定）
  * ph        Page-Hinkley（累积偏差超过 delta 报警）
  * ewma      指数加权移动平均（L 倍 sigma 控制限）

序列模型：基线是 lognormal（比值型指标本来就是乘性的），
在随机位置注入**乘性下移**（1-r），r 是我们要发现的相对退步。

用法:
    python tools/detectors.py                 # 跑完整对比表
    python tools/detectors.py --reps 2000     # 更稳但更慢
"""
from __future__ import annotations

import math
import random
import statistics
import sys

SIGMA_LOG = 0.5  # 比值型指标的保守离散度（与 cohort_check 一致）


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def sample_series(n, baseline=-3.0, sigma=SIGMA_LOG, change_at=None, ratio=1.0, rng=None):
    """生成 lognormal 序列；change_at 之后乘以 ratio（<1 表示退步）。"""
    rng = rng or random.Random()
    out = []
    for i in range(n):
        shift = math.log(ratio) if (change_at is not None and i >= change_at) else 0.0
        out.append(math.exp(rng.gauss(baseline + shift, sigma)))
    return out


def detect_rule3(values, median, drop=0.30, streak=3):
    threshold = median * (1 - drop / 2)
    count = 0
    for i, v in enumerate(values):
        count = count + 1 if v < threshold else 0
        if count >= streak:
            return i
    return None


def detect_cusum(values, median, sigma=SIGMA_LOG, drift=0.5, threshold=5.0):
    """标准化 CUSUM：累积 (baseline - log v)/sigma 的正偏差，超过 h 报警。"""
    ref = math.log(median) if median > 0 else None
    if ref is None:
        return None
    pos = 0.0
    for i, v in enumerate(values):
        if v <= 0:
            continue
        z = (ref - math.log(v)) / sigma   # 下移为正
        pos = max(0.0, pos + z - drift)
        if pos > threshold:
            return i
    return None


def detect_ph(values, median, sigma=SIGMA_LOG, delta=1.0):
    ref = math.log(median) if median > 0 else None
    if ref is None:
        return None
    total = 0.0
    minimum = 0.0
    for i, v in enumerate(values):
        if v <= 0:
            continue
        total += (ref - math.log(v)) / sigma
        minimum = min(minimum, total)
        if total - minimum > delta:
            return i
    return None


def detect_ewma(values, median, sigma=SIGMA_LOG, lam=0.3, limit=3.0):
    ref = math.log(median) if median > 0 else None
    if ref is None:
        return None
    level = ref
    for i, v in enumerate(values):
        if v <= 0:
            continue
        z = (math.log(v) - ref) / sigma
        level = (1 - lam) * level + lam * (ref + z * sigma)
        if level < ref - limit * sigma * math.sqrt(lam / (2 - lam)):
            return i
    return None


DETECTORS = {
    "rule3": lambda values, median: detect_rule3(values, median),
    "cusum": lambda values, median: detect_cusum(values, median),
    "ph": lambda values, median: detect_ph(values, median),
    "ewma": lambda values, median: detect_ewma(values, median),
}


def evaluate(reps=600, length=28, ratios=(1.0, 0.8, 0.7, 0.5), seed=7):
    """返回 {方法: {ratio: (平均延迟, 检出率, 误报率)}}。"""
    rng = random.Random(seed)
    results = {name: {} for name in DETECTORS}
    for ratio in ratios:
        delays = {name: [] for name in DETECTORS}
        hits = {name: 0 for name in DETECTORS}
        for _ in range(reps):
            change_at = None if ratio == 1.0 else length // 2
            values = sample_series(length, change_at=change_at, ratio=ratio, rng=rng)
            # 基线用前一半（或全体）估，模拟"用历史窗口当基线"
            median = statistics.median(values[: change_at or length])
            for name, fn in DETECTORS.items():
                at = fn(values, median)
                if at is None:
                    continue
                if change_at is None:
                    # 无变化却报警 = 误报
                    hits[name] += 1
                elif at >= change_at:
                    hits[name] += 1
                    delays[name].append(at - change_at)
        for name in DETECTORS:
            mean_delay = statistics.mean(delays[name]) if delays[name] else float("nan")
            results[name][ratio] = (mean_delay, hits[name] / reps)
    return results


def false_alarm_rate(h, reps=400, length=28, seed=11):
    rng = random.Random(seed)
    alarms = 0
    for _ in range(reps):
        values = sample_series(length, rng=rng)
        median = statistics.median(values)
        if detect_cusum(values, median, threshold=h) is not None:
            alarms += 1
    return alarms / reps


def calibrate(target_per_window=0.05, reps=400):
    """找到让「单窗口误报率 <= target」的最小 h（越小越灵敏）。"""
    for h in (3, 4, 5, 6, 7, 8, 9, 10, 12):
        rate = false_alarm_rate(h, reps=reps)
        if rate <= target_per_window:
            return h, rate
    return 12, false_alarm_rate(12, reps=reps)


def main(argv):
    if "--calibrate" in argv:
        h, rate = calibrate()
        print("CUSUM 标定：h=%.0f 时单窗口误报率 %.1f%%（年化约 %.0f%%）" % (h, rate * 100, rate * 1300 / 100))
        return 0
    reps = 600
    if "--reps" in argv:
        reps = int(argv[argv.index("--reps") + 1])
    results = evaluate(reps=reps)
    print("检测器对比：序列长度 28，sigma(log)=%.1f，每次 %d 次重复" % (SIGMA_LOG, reps))
    print("读法：延迟 = 变化发生后平均几天发现；检出率 = 召回的样本比例")
    print()
    header = "%-8s" % "方法"
    for ratio in (1.0, 0.8, 0.7, 0.5):
        label = "无变化(误报)" if ratio == 1.0 else "退 %.0f%%" % ((1 - ratio) * 100)
        header += "%-18s" % label
    print(header)
    print("-" * len(header))
    for name in DETECTORS:
        row = "%-8s" % name
        for ratio in (1.0, 0.8, 0.7, 0.5):
            delay, rate = results[name][ratio]
            if ratio == 1.0:
                row += "%-18s" % ("%.0f%%" % (rate * 100))
            else:
                row += "%-18s" % ("%.1f 天 / %.0f%%" % (delay, rate * 100) if delay == delay else "未检出")
        print(row)
    print()
    print("注：误报率是 28 天窗口内的比例；年化大致 × 13。")
    return 0


if __name__ == "__main__":
    _force_utf8()
    sys.exit(main(sys.argv[1:]))