#!/usr/bin/env python3
"""register_videos —— 按 BVID 批量登记视频（因为空间枚举接口被风控挡住了）。

背景（实测 2026-10-25）：
  * 单条取数 x/web-interface/view?bvid=   → code=0，可用
  * 空间枚举 x/space/arc/search           → code=-799 请求过于频繁
  * 空间枚举 x/space/wbi/arc/search       → code=-352 风控校验失败

结论：**不要靠爬列表**。让用户从创作中心复制一份 BVID 列表，我们按 BVID 逐条取数 ——
既不会把账号打到风控里，也不需要任何登录态。

用法:
    python tools/register_videos.py bvids.txt --cohort tutorial --out runs
    cat bvids.txt | python tools/register_videos.py - --cohort tutorial
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_stats as fs  # noqa: E402


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def read_bvids(source):
    if source == "-":
        text = sys.stdin.read()
    else:
        text = Path(source).read_text(encoding="utf-8-sig")
    seen = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        token = line.split()[0]
        if token.startswith("BV") and token not in seen:
            seen.append(token)
    return seen


def main(argv):
    if not argv:
        print("用法：python tools/register_videos.py <bvids.txt|-> [--cohort 名称] [--out runs]")
        return 2
    source = argv[0]
    cohort = argv[argv.index("--cohort") + 1] if "--cohort" in argv else "default"
    out = Path(argv[argv.index("--out") + 1] if "--out" in argv else "runs")

    bvids = read_bvids(source)
    if not bvids:
        print("没读到任何 BVID（每行一个，或以 BV 开头）", file=sys.stderr)
        return 1

    ok = skipped = failed = 0
    for bvid in bvids:
        try:
            payload = fs.default_transport(fs.API + bvid)
            fields = fs.parse(payload)
        except Exception as exc:
            print("跳过 %s：%s" % (bvid, str(exc)[:80]), file=sys.stderr)
            failed += 1
            continue
        day = datetime.fromtimestamp(fields.get("pubdate") or 0).strftime("%Y-%m-%d")
        run = out / ("%s-%s" % (day, bvid))
        if run.exists():
            skipped += 1
            continue
        run.mkdir(parents=True, exist_ok=True)
        stamp = day + "T20:00:00+08:00"
        events = [
            {"type": "topic.pick", "at": stamp, "cohort": cohort,
             "options": [{"title": fields.get("title")}, {"title": "（历史视频，无备选）"}],
             "chosen": 0, "why_only_one": "这是已发布的历史视频，不是当天的选题过程"},
            {"type": "publish", "at": stamp, "bvid": bvid},
            fs.to_event(fields),
        ]
        (run / "events.jsonl").write_text(
            chr(10).join(json.dumps(e, ensure_ascii=False) for e in events) + chr(10), encoding="utf-8")
        ok += 1
        print("登记 %s  %s  播放 %s" % (bvid, str(fields.get("title"))[:28], fields.get("views")))

    print()
    print("结果：新登记 %d 条，已存在跳过 %d 条，失败 %d 条" % (ok, skipped, failed))
    return 0 if ok or skipped else 1


if __name__ == "__main__":
    _force_utf8()
    sys.exit(main(sys.argv[1:]))
