"""ReplayStore —— 把每一次接口响应录下来，之后离线重放。

为什么：B站接口有风控（-352/-799），测试和演示都不该依赖它的可用性。
录一次、之后永远离线跑 —— 这和 agenttest 的 cassette 是同一个思路，
只不过这里的「事件」是一次 HTTP 交换。

磁盘格式（JSONL，一行一次交换，带 sha256 链）：
    {"key": "<规范化后的请求>", "response": {...}, "hash": "...", "prev": "..."}
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

STORE_NAME = "exchanges.jsonl"


def canonical_request(method: str, url: str, params: dict | None) -> str:
    params = params or {}
    pairs = "&".join("%s=%s" % (k, params[k]) for k in sorted(params) if k not in ("wts", "w_rid"))
    return "%s %s?%s" % (method.upper(), url.rsplit("?", 1)[0], pairs)


def _digest(entry: dict) -> str:
    body = {"key": entry["key"], "response": entry["response"], "prev": entry.get("prev")}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class ReplayStore:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / STORE_NAME
        self.entries = {}
        self.head = None
        if self.path.exists():
            self._load()

    def _load(self):
        prev = None
        for lineno, line in enumerate(self.path.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            expected = _digest(entry)
            if entry.get("hash") != expected:
                raise ValueError("第 %d 条交换的哈希对不上（文件被改过？）" % lineno)
            if entry.get("prev") != prev:
                raise ValueError("第 %d 条交换的链断了" % lineno)
            self.entries[entry["key"]] = entry["response"]
            prev = entry["hash"]
        self.head = prev

    def get(self, key: str):
        return self.entries.get(key)

    def put(self, key: str, response: dict):
        entry = {"key": key, "response": response, "prev": self.head}
        entry["hash"] = _digest(entry)
        self.head = entry["hash"]
        self.entries[key] = response
        self.root.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + chr(10))

    def __len__(self):
        return len(self.entries)
