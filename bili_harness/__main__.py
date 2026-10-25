"""命令行入口：python -m bili_harness <cmd>

  record <out_dir>            用 live 打一次 popular，录进 store（不碰空间接口）
  replay <store_dir>          从 store 重放并打印条数
  video <bvid>                单条取数（live）
"""
from __future__ import annotations

import json
import sys

from .client import Harness
from .errors import BiliError


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    try:
        if cmd == "record":
            out = argv[1] if len(argv) > 1 else "fixtures"
            h = Harness(mode="record", store_root=out)
            payload = h.popular(size=5)
            print("已录 %d 次交换到 %s" % (len(h.store), out))
            print("样例：", ", ".join(str(v.get("bvid")) for v in ((payload.get("data") or {}).get("list") or [])[:5]))
            return 0
        if cmd == "replay":
            store = argv[1] if len(argv) > 1 else "fixtures"
            h = Harness(mode="replay", store_root=store)
            payload = h.popular(size=5)
            items = (payload.get("data") or {}).get("list") or []
            print("回放成功：%d 条交换，样例 %d 条视频" % (len(h.store), len(items)))
            return 0
        if cmd == "video":
            if len(argv) < 2:
                print("用法：python -m bili_harness video <bvid>", file=sys.stderr)
                return 2
            h = Harness(mode="live", per_minute=10)
            payload = h.video(argv[1])
            data = payload.get("data") or {}
            print(json.dumps({"bvid": data.get("bvid"), "title": data.get("title"),
                              "views": (data.get("stat") or {}).get("view")}, ensure_ascii=False))
            return 0
    except BiliError as exc:
        print("接口错误：%s（可重试=%s，需人工=%s）" % (exc, exc.retryable, exc.needs_human), file=sys.stderr)
        return 1
    except KeyError as exc:
        print("回放缺条目：%s" % exc, file=sys.stderr)
        return 1
    print("未知命令：" + cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
