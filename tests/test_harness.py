"""harness：签名、存储、错误分类、预算、回放 —— 全部离线可测。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bili_harness import Budget, BiliError, Harness, ReplayStore, canonical_request  # noqa: E402
from bili_harness import sign  # noqa: E402


def test_canonical_request_ignores_volatile_params():
    a = canonical_request("get", "https://x/y", {"b": 2, "a": 1, "wts": 111, "w_rid": "z"})
    b = canonical_request("GET", "https://x/y", {"a": 1, "b": 2, "wts": 999, "w_rid": "q"})
    assert a == b
    assert a.startswith("GET ")


def test_sign_is_deterministic_and_sorted():
    img = "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png"
    sub = "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"
    one = sign.sign({"mid": 1, "pn": 1}, img, sub, now=1700000000)
    two = sign.sign({"pn": 1, "mid": 1}, img, sub, now=1700000000)
    assert one["w_rid"] == two["w_rid"]
    assert one["wts"] == 1700000000


def test_mixin_key_uses_the_table_and_truncates():
    img = "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png"
    sub = "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"
    key = sign.mixin_key(img, sub)
    assert len(key) == 32
    assert key.isalnum()


def test_store_roundtrip_and_chain(tmp_path):
    store = ReplayStore(tmp_path)
    store.put("GET a", {"code": 0, "n": 1})
    store.put("GET b", {"code": 0, "n": 2})
    reloaded = ReplayStore(tmp_path)
    assert reloaded.get("GET a")["n"] == 1
    assert len(reloaded) == 2


def test_tampered_store_is_rejected(tmp_path):
    store = ReplayStore(tmp_path)
    store.put("GET a", {"code": 0})
    path = tmp_path / "exchanges.jsonl"
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    entry["response"]["code"] = 1
    path.write_text(json.dumps(entry, ensure_ascii=False, sort_keys=True) + chr(10), encoding="utf-8")
    with pytest.raises(ValueError):
        ReplayStore(tmp_path)


def test_replay_mode_never_calls_the_network(tmp_path):
    store = ReplayStore(tmp_path)
    url = "https://api.bilibili.com/x/web-interface/view"
    store.put(canonical_request("GET", url, {"bvid": "BV1"}), {"code": 0, "data": {"bvid": "BV1"}})

    calls = []

    def exploding(url, params):
        calls.append(url)
        raise AssertionError("replay 模式不该联网")

    h = Harness(mode="replay", store_root=tmp_path, transport=exploding)
    assert h.video("BV1")["code"] == 0
    assert calls == []


def test_replay_miss_is_loud(tmp_path):
    h = Harness(mode="replay", store_root=tmp_path, transport=lambda u, p: {})
    with pytest.raises(KeyError):
        h.video("BV_missing")


def test_record_mode_persists_the_exchange(tmp_path):
    url = "https://api.bilibili.com/x/web-interface/view"
    h = Harness(mode="record", store_root=tmp_path, transport=lambda u, p: {"code": 0, "data": {"bvid": p["bvid"]}})
    h.video("BV9")
    again = Harness(mode="replay", store_root=tmp_path, transport=lambda u, p: {})
    assert again.video("BV9")["data"]["bvid"] == "BV9"


def test_error_taxonomy_separates_rate_limit_from_risk_control():
    limited = BiliError(-799, "请求过于频繁")
    risk = BiliError(-352, "风控校验失败")
    assert limited.retryable is True and limited.needs_human is False
    assert risk.needs_human is True and risk.retryable is False


def test_risk_control_raises_instead_of_retrying(tmp_path):
    h = Harness(mode="live", store_root=tmp_path, transport=lambda u, p: {"code": -352, "message": "风控校验失败"})
    with pytest.raises(BiliError) as exc:
        h.video("BV1")
    assert exc.value.needs_human is True


def test_budget_blocks_the_nth_call():
    budget = Budget(per_minute=2)
    budget.spend()
    budget.spend()
    with pytest.raises(RuntimeError):
        budget.spend()


def test_live_mode_with_budget_of_zero_refuses_immediately(tmp_path):
    h = Harness(mode="live", store_root=tmp_path, per_minute=0, transport=lambda u, p: {"code": 0})
    with pytest.raises(RuntimeError):
        h.video("BV1")
