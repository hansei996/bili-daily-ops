# bili-daily-ops

> 让一个 B站账号**持续日更**，并且每次都比上次更清楚为什么有效。

不是「AI 一键生成视频」。生成是红海且模型每天都在变强；这个仓只碰**判断**——今天该拍什么、这条能不能进流水线、这次退步退在哪一环。

## 当前假设（来自 PAIN.md）

日更最容易断在 **S0「当天定题」**：它是唯一**没有降级品**的一站（剪辑能砍特效、审核能用兜底稿，选题砸了只能交零），而且「今天不做也不会立刻疼」，于是决策被推到一天里最贵的时候——晚开工 → 降质 → 数据差 → 更不想做，是断更的复利循环。

所以先做的不是「生成选题」，而是**守门 + 库存**。

## 两把闸门（已实现）

### 1. 选题准入卡 `tools/topic_gate.py`

卡 A 五条全过才入库：

| # | 规则 | 不过会怎样 |
|---|---|---|
| A1 | 三行齐（谁遇到 / 现在怎么错 / 看完能立刻做什么） | 那不是选题，只是念头 |
| A2 | 素材 30 分钟内可得 → daily；否则 → weekend | 排不进日更档 |
| A3 | 可证伪：写出 metric 与 metric_baseline | 「看反响」不算标准 |
| A4 | 能指出同类内容的最弱一环 | 说不出说明我们也不更强 |
| A5 | 至少一条反直觉结论 | 复述常识，点击率天花板很低 |

```bash
python tools/topic_gate.py check examples/topics.jsonl
# 入库  [daily] 3 个把 Claude 用废的坏习惯
# 打回  随便聊聊最近的 AI
#         [A1] 三行不齐：who/wrong_now/can_do_after 缺一项就不是选题，只是念头
```

### 2. 库存水位 `topic_gate.py backlog`

```bash
python tools/topic_gate.py backlog examples/topics.jsonl --days 7
# 日更档库存：1 条（要求 >= 7）
# FAIL  库存不足，缺 6 条。按 PAIN.md 3.1：今天第一件事是补库，不是拍片。
```

### 3. 记录格式 `tools/validate_run.py`

一条视频 = 一份 `events.jsonl`（选题 → 标题 → 封面 → 发布 → 24h 数据 → 复盘）。先把口径钉死再谈判断，否则「这条不如上条」永远说不清。

```bash
python tools/validate_run.py examples
# PASS  good
# FAIL  bad-pct
#    [V4] 第 2 行  ctr 必须是 0-1 的比例，收到 6.1（不要填百分数）
```

## 不能结构化的部分（别自欺）

- **会不会火**：只能同题材 n≥5 的事后对照，事前预测就是猜
- **表达风格**：不可清单化
- **题材上限**：卡片只保下限与节奏，不保上限

## 测试

```bash
python -m pytest tests -q      # 9 passed
```
