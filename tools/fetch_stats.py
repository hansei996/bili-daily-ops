#!/usr/bin/env python3
"""fetch_stats —— 从 B站公开接口取一条视频的真实数字，写成 metrics 事件。

为什么不用创作中心导出的 CSV：据 ENGINEERING.md §1.2 核对，那份只是账号级日聚合
（日期 + 播放两列），逐条拿不到；OCR 会把「万/亿」和浮点完播率错成静默错误。

诚实边界（必须写在使用者看得见的地方）：
  * 公开接口给的是**累计值**，没有「发布后满 24 小时」这个时点。
    所以本工具落一个 snapshot_at 字段，记录我们真正取数的时刻；
    at_hours 是「发布到取数经过了多少小时」，**它是近似，不是精确的 T+24h**。
  * completion 需要 duration 与「平均播放时长」，后者公开接口不给 ——
    所以这里只写 views/likes/coins/favorites/replies/shares/danmaku 与 ctr（若能拿到）。
    完播率缺失就**留空**，不猜。

用法:
    python tools/fetch_stats.py BV1xx411c7mD --run-dir runs/2026-10-19-run
    python tools/fetch_stats.py BV1xx411c7mD --json        # 只看取到的原始字段
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.bilibili.com/x/web-interface/view?bvid="
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


def default_transport(url, timeout=20):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def parse(payload):
    """把接口返回体变成我们的事件字段；不认识就明确报错，不要静默出空值。"""
    if not isinstance(payload, dict):
        raise ValueError("返回体不是 JSON 对象")
    if payload.get("code") != 0:
        raise ValueError("接口返回 code=%r message=%r" % (payload.get("code"), payload.get("message")))
    data = payload.get("data") or {}
    stat = data.get("stat") or {}
    if "view" not in stat:
        raise ValueError("返回体里没有 stat.view：接口结构可能变了")
    return {
        "bvid": data.get("bvid"),
        "title": data.get("title"),
        "pubdate": data.get("pubdate"),
        "duration_sec": data.get("duration"),
        "views": stat.get("view"),
        "likes": stat.get("like"),
        "coins": stat.get("coin"),
        "favorites": stat.get("favorite"),
        "replies": stat.get("reply"),
        "shares": stat.get("share"),
        "danmaku": stat.get("danmaku"),
    }


def hours_since(pubdate, now):
    if not pubdate:
        return None
    return round((now - float(pubdate)) / 3600.0, 2)


def to_event(fields, now=None):
    now = now or time.time()
    hours = hours_since(fields.get("pubdate"), now)
    event = {
        "type": "metrics",
        "at": datetime.fromtimestamp(now, timezone.utc).astimezone().isoformat(timespec="seconds"),
        "snapshot_at": datetime.fromtimestamp(now, timezone.utc).astimezone().isoformat(timespec="seconds"),
        "at_hours": 24 if (hours or 0) <= 48 else 72,
        "hours_since_publish": hours,
        "views": fields.get("views"),
        "likes": fields.get("likes"),
        "coins": fields.get("coins"),
        "favorites": fields.get("favorites"),
        "replies": fields.get("replies"),
        "shares": fields.get("shares"),
        "danmaku": fields.get("danmaku"),
        "duration_sec": fields.get("duration_sec"),
        "source": "bilibili.web-interface.view",
    }
    return event


def append_event(run_dir, event):
    path = Path(run_dir) / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + chr(10))
    return path


def main(argv):
    if not argv:
        print("用法：python tools/fetch_stats.py <BVID> [--run-dir DIR] [--json] [--transport fake.json]")
        return 2
    bvid = argv[0]
    run_dir = argv[argv.index("--run-dir") + 1] if "--run-dir" in argv else None
    only_json = "--json" in argv

    if "--transport" in argv:
        fixture = Path(argv[argv.index("--transport") + 1])
        payload = json.loads(fixture.read_text(encoding="utf-8"))
    else:
        try:
            payload = default_transport(API + bvid)
        except Exception as exc:
            print("取数失败：%s" % exc, file=sys.stderr)
            return 1

    try:
        fields = parse(payload)
    except ValueError as exc:
        print("返回体不认识：%s" % exc, file=sys.stderr)
        return 1

    if only_json:
        print(json.dumps(fields, ensure_ascii=False, indent=2))
        return 0

    event = to_event(fields)
    if not run_dir:
        print(json.dumps(event, ensure_ascii=False, indent=2))
        return 0
    path = append_event(run_dir, event)
    print("已写入 %s" % path)
    print("  播放 %s · 点赞 %s · 币 %s · 收藏 %s · 评论 %s"
          % (event["views"], event["likes"], event["coins"], event["favorites"], event["replies"]))
    print("  发布到取数经过 %.1f 小时（at_hours 记为 %d，这是近似而非精确 T+24h）"
          % (event["hours_since_publish"] or 0, event["at_hours"]))
    return 0


if __name__ == "__main__":
    _force_utf8()
    sys.exit(main(sys.argv[1:]))
