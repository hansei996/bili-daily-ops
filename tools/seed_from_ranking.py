#!/usr/bin/env python3
"""seed_from_ranking —— 用真实榜单数据建一份「同题材基线」。

用途：cohort_check 需要一个**窗口外基线**才能判退步。自己没有足够历史时，
可以用同一分区的真实数据当参照——但要说清它是什么：**别人的视频**，不是你的历史。

诚实边界：
  * 这里的数据是「抓取时刻的累计值」，不同视频发布时长差几个月到几年，
    所以只能用**比值型指标**（互动率），不能比绝对值播放量；
  * 完播率拿不到（接口不给平均播放时长），所以不写 avg_view_sec。

用法:
    python tools/seed_from_ranking.py --top 20 --cohort real-ranking --out _baseline-real
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

SOURCES = {
    "ranking": "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all",
    "popular": "https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1",
}
API = SOURCES["ranking"]

# 实测：ranking 端点在连续请求后会返回 -352（风控），popular 通常仍可用。
RATE_LIMITED = -352
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def fetch(url=API):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def slug(text):
    keep = [ch for ch in str(text) if ch.isalnum()]
    return ("".join(keep)[:16] or "video")


def events_for(item, cohort, snapshot_at):
    stat = item.get("stat") or {}
    bvid = item.get("bvid")
    return [
        {
            "type": "topic.pick",
            "at": snapshot_at,
            "cohort": cohort,
            "options": [{"title": item.get("title")}, {"title": "（基线样本，无备选）"}],
            "chosen": 0,
            "why_only_one": "这是别人的视频，用来当同题材基线，不是我们的选题过程",
        },
        {"type": "publish", "at": datetime.fromtimestamp(item.get("pubdate") or 0).astimezone().isoformat(timespec="seconds"),
         "bvid": bvid},
        {
            "type": "metrics",
            "at": snapshot_at,
            "snapshot_at": snapshot_at,
            "at_hours": 72,
            "hours_since_publish": None,
            "views": stat.get("view"),
            "likes": stat.get("like"),
            "coins": stat.get("coin"),
            "favorites": stat.get("favorite"),
            "replies": stat.get("reply"),
            "shares": stat.get("share"),
            "danmaku": stat.get("danmaku"),
            "duration_sec": item.get("duration"),
            "source": "bilibili.web-interface.ranking",
        },
    ]


def load_payload(source, transport=None):
    if transport:
        return json.loads(Path(transport).read_text(encoding="utf-8"))
    return fetch(SOURCES.get(source, API))


def main(argv):
    top = 20
    cohort = "real-ranking"
    out = Path("_baseline-real")
    for index, flag in enumerate(argv):
        if flag == "--top" and index + 1 < len(argv):
            top = int(argv[index + 1])
        if flag == "--cohort" and index + 1 < len(argv):
            cohort = argv[index + 1]
        if flag == "--out" and index + 1 < len(argv):
            out = Path(argv[index + 1])

    source = argv[argv.index("--source") + 1] if "--source" in argv else "ranking"
    transport = argv[argv.index("--transport") + 1] if "--transport" in argv else None
    payload = load_payload(source, transport)
    if payload.get("code") == RATE_LIMITED and source == "ranking" and not transport:
        print("ranking 被风控（code=-352），改用 popular 重试……", file=sys.stderr)
        source = "popular"
        payload = load_payload(source)
    if payload.get("code") != 0:
        print("接口返回 code=%r message=%r（换 --source popular 试试）"
              % (payload.get("code"), payload.get("message")), file=sys.stderr)
        return 1
    items = ((payload.get("data") or {}).get("list") or [])[:top]
    if not items:
        print("榜单是空的", file=sys.stderr)
        return 1

    snapshot_at = datetime.now().astimezone().isoformat(timespec="seconds")
    written = 0
    for item in items:
        stat = item.get("stat") or {}
        if not stat.get("view") or not item.get("duration"):
            continue
        run = out / ("%s-%s" % (datetime.fromtimestamp(item.get("pubdate") or 0).strftime("%Y-%m-%d"), slug(item.get("bvid"))))
        run.mkdir(parents=True, exist_ok=True)
        body = chr(10).join(json.dumps(e, ensure_ascii=False) for e in events_for(item, cohort, snapshot_at)) + chr(10)
        (run / "events.jsonl").write_text(body, encoding="utf-8")
        written += 1

    print("已写入 %d 条真实基线到 %s（cohort=%s，抓取时刻 %s）" % (written, out, cohort, snapshot_at))
    print("提醒：这是**别人的视频**的累计值，只能比比值型指标，不能比绝对播放量。")
    return 0 if written else 1


if __name__ == "__main__":
    _force_utf8()
    sys.exit(main(sys.argv[1:]))