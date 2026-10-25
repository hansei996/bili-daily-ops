"""Harness —— 三种模式：live / record / replay。

- live    直接打接口，带预算与退避；撞到 -352 立刻停手（不重试）
- record  live + 把每次交换写进 store
- replay  只读 store，绝不联网（测试与演示用这个）

预算（budget）是硬约束：默认 30 次/分钟。
B站的限流是按 IP 的，所以「慢一点」不是客气，是让工具能长期用下去。
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from . import errors, sign
from .store import ReplayStore, canonical_request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
NAV = "https://api.bilibili.com/x/web-interface/nav"


class Budget:
    def __init__(self, per_minute=30):
        self.per_minute = per_minute
        self.calls = []

    def spend(self):
        now = time.time()
        self.calls = [t for t in self.calls if now - t < 60]
        if len(self.calls) >= self.per_minute:
            raise RuntimeError("预算用尽：每分钟最多 %d 次，已用 %d 次" % (self.per_minute, len(self.calls)))
        self.calls.append(now)


class Harness:
    def __init__(self, mode="replay", store_root="fixtures", per_minute=30, cookie=None, transport=None):
        if mode not in ("live", "record", "replay"):
            raise ValueError("mode 只能是 live / record / replay")
        self.mode = mode
        self.store = ReplayStore(store_root)
        self.budget = Budget(per_minute)
        self.cookie = cookie
        self._transport = transport or self._http
        self._wbi = None

    # -- 传输 ---------------------------------------------------------
    def _http(self, url, params):
        full = url + ("?" + urllib.parse.urlencode(params) if params else "")
        headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        request = urllib.request.Request(full, headers=headers)
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8", "replace"))

    def get(self, url, params=None, signed=False):
        params = dict(params or {})
        if signed:
            params = self.with_wbi(url, params)
        key = canonical_request("GET", url, params)
        if self.mode == "replay":
            hit = self.store.get(key)
            if hit is None:
                raise KeyError("回放里没有这次请求（先用 record 模式录一次）：" + key)
            return hit
        self.budget.spend()
        payload = self._transport(url, params)
        code = payload.get("code")
        if code != 0:
            raise errors.classify(code, payload.get("message", ""), url)
        if self.mode == "record":
            self.store.put(key, payload)
        return payload

    # -- WBI ----------------------------------------------------------
    def with_wbi(self, url, params):
        if self._wbi is None:
            nav = self._transport(NAV, {})
            data = nav.get("data") or {}
            wbi = data.get("wbi_img") or {}
            self._wbi = (wbi.get("img_url", ""), wbi.get("sub_url", ""))
        return sign.sign(params, self._wbi[0], self._wbi[1])

    # -- 便捷方法 ------------------------------------------------------
    def video(self, bvid):
        return self.get("https://api.bilibili.com/x/web-interface/view", {"bvid": bvid})

    def popular(self, page=1, size=20):
        return self.get("https://api.bilibili.com/x/web-interface/popular", {"pn": page, "ps": size})

    def space(self, mid, page=1, size=30):
        return self.get(
            "https://api.bilibili.com/x/space/wbi/arc/search",
            {"mid": mid, "pn": page, "ps": size, "order": "pubdate"},
            signed=True,
        )
