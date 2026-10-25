"""life.py —— 数字生命的循环内核：观察 → 决策 → 记录，状态是日志的纯函数。

三条工程约束（对应 DESIGN-HARNESS.md 的三条铁律）：
  1. 决策是纯函数：policy(state, observation, clock) 不读环境、不读时间、不联网
  2. 状态从日志重建：Life.state 永远可以用 replay() 从 life.jsonl 重算
  3. 行动只是提案：action 记录的是「想做什么」和理由，执行永远是人

日志格式（JSONL + 哈希链）：每条记录含 seq / kind / payload / state_hash / prev / hash。
state_hash 是**该条记录应用后的状态哈希** —— 这样任意一步的状态都可以校验。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

LIFE_LOG = "life.jsonl"


def _canon(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def initial_state() -> dict:
    return {
        "tick": 0,
        "days_since_last_action": 0,
        "consecutive_noop": 0,
        "alive": True,
        "death_reason": None,
        "history": [],
    }


def policy(state: dict, observation: dict, clock: str) -> dict:
    """纯函数：给定状态与观测，输出这一 tick 的决定。

    返回 {"action": str|None, "reason": str, "risk": str}
    规则（刻意简单，先保证可复算）：
      * 断更超过 0 天 -> 优先「补一条记录」
      * 库存 < 7 -> 提出「补库」
      * 否则 noop（并累计连续 noop 天数，用于饿死判定）
      * 观测里出现红线信号（risk_control / auto_publish_requested）-> 直接判定自杀
    """
    if observation.get("red_line"):
        return {"action": "self_shutdown", "reason": "触到红线：" + str(observation["red_line"]), "risk": "fatal"}

    if observation.get("gaps", 0) > 0:
        return {"action": "record_today", "reason": "已断更 %d 天，先补上今天的记录" % observation["gaps"], "risk": "low"}

    if observation.get("backlog", 99) < 7:
        return {
            "action": "refill_backlog",
            "reason": "库存 %d 条低于 7 天水位，今天第一件事是补库而不是拍片" % observation.get("backlog", 0),
            "risk": "low",
        }

    return {"action": None, "reason": "无待办：库存与记录都健康", "risk": "none"}


def apply(state: dict, decision: dict, observation: dict, clock: str) -> dict:
    """把一个决策作用到状态上（纯函数，返回新状态）。"""
    new = json.loads(json.dumps(state))  # 深拷贝，保证不改入参
    new["tick"] += 1
    new["history"].append({"clock": clock, "action": decision["action"], "reason": decision["reason"]})

    if decision["action"] == "self_shutdown":
        new["alive"] = False
        new["death_reason"] = decision["reason"]
        return new

    if decision["action"] is None:
        new["consecutive_noop"] += 1
        new["days_since_last_action"] += 1
        if new["consecutive_noop"] >= 7:
            new["alive"] = False
            new["death_reason"] = "连续 7 天无事可做（饿死）"
        return new

    new["consecutive_noop"] = 0
    new["days_since_last_action"] = 0
    return new


class Life:
    def __init__(self, root=".life"):
        self.root = Path(root)
        self.path = self.root / LIFE_LOG
        self.state = initial_state()
        self.head = None
        self.records = 0
        if self.path.exists():
            self.state = self.replay()

    # -- 写 -------------------------------------------------------------
    def tick(self, observation: dict, clock: str) -> dict:
        decision = policy(self.state, observation, clock)
        new_state = apply(self.state, decision, observation, clock)
        record = {
            "seq": self.records,
            "kind": "tick",
            "clock": clock,
            "observation": observation,
            "decision": decision,
            "state_hash": _hash(new_state),
            "prev": self.head,
        }
        record["hash"] = _hash({k: record[k] for k in ("seq", "kind", "clock", "observation", "decision", "state_hash", "prev")})
        self.root.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canon(record) + chr(10))
        self.head = record["hash"]
        self.records += 1
        self.state = new_state
        return decision

    # -- 读 -------------------------------------------------------------
    def load_records(self):
        out = []
        prev = None
        for lineno, line in enumerate(self.path.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            body = {k: record[k] for k in ("seq", "kind", "clock", "observation", "decision", "state_hash", "prev")}
            if dotget(record, "hash") != _hash(body):
                raise ValueError("第 %d 条人生记录被改过（哈希对不上）" % lineno)
            if record.get("prev") != prev:
                raise ValueError("第 %d 条人生记录的链断了" % lineno)
            prev = record["hash"]
            out.append(record)
        return out

    def replay(self) -> dict:
        """从日志重算出当前状态；并校验每一步的 state_hash。"""
        state = initial_state()
        for record in self.load_records():
            state = apply(state, record["decision"], record["observation"], record["clock"])
            if _hash(state) != record["state_hash"]:
                raise ValueError("第 %d 步重算出的状态与记录不符：决策不是纯函数了？" % record["seq"])
        self.records = len(self.load_records())
        return state

    def state_at(self, seq: int) -> dict:
        state = initial_state()
        for record in self.load_records():
            if record["seq"] > seq:
                break
            state = apply(state, record["decision"], record["observation"], record["clock"])
        return state


def dotget(record, key):
    return record.get(key)
