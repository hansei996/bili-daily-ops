"""WBI 签名：B站空间/搜索类接口需要它。

算法（公开的混淆表 + 截断）：
  img_key + sub_key -> 按 MIXIN 表重排 -> 取前 32 位 = mixin_key
  w_rid = md5(query + mixin_key)，query 是按键名排序的 urlencode，含 wts
"""
from __future__ import annotations

import hashlib
import time
import urllib.parse

MIXIN = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


def key_from_url(url: str) -> str:
    """从 https://.../7cd084941338484aae1ad9425b84077c.png 里取出文件名部分。"""
    name = url.rsplit("/", 1)[-1]
    return name.split(".")[0]


def mixin_key(img_url: str, sub_url: str) -> str:
    raw = key_from_url(img_url) + key_from_url(sub_url)
    return "".join(raw[i] for i in MIXIN if i < len(raw))[:32]


def sign(params: dict, img_url: str, sub_url: str, now: float | None = None) -> dict:
    key = mixin_key(img_url, sub_url)
    payload = dict(params)
    payload["wts"] = int(now if now is not None else time.time())
    query = urllib.parse.urlencode(sorted(payload.items()))
    payload["w_rid"] = hashlib.md5((query + key).encode("utf-8")).hexdigest()
    return payload
