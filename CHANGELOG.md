# 变更记录

## 2026-10-25 · F9 能力自检升到 8 条，并把它当成唯一对外入口

`python tools/status.py` 现在覆盖 8 项能力，**全部离线可跑**（用 fixture 而不是真接口）：

新增两条：

- 真实接口数据能建成合规基线（用 `ranking.json` fixture 播种再校验）
- 风控时报错而不是空跑（用 `-352` fixture，必须 exit 1 且输出里带 code）

三条测试锁住它：8 条全过、做不到清单里必须有那三句、**源码里不许出现 urllib**（能力自检不该联网）。

测试：41 passed。

## 2026-10-25 · F8 风控回退 + 离线可测

**实测发现**：`ranking/v2` 端点在连续请求后返回 `code=-352`（风控）；`popular` 仍可用。
这不是理论问题——我第一次抓 15 条成功，隔几分钟再抓就是 -352。

处理：

- `seed_from_ranking` 加 `--source ranking|popular`；遇到 -352 自动回退到 popular 并**在 stderr 说明**
- 加 `--transport <json>`：用录好的 fixture 跑，测试不联网
- fixture `examples/fixtures/ranking.json` 存了 3 条真实条目（bvid/title/pubdate/duration/stat）

**测试 38 passed**（新增 5 条）：fixture 形状、离线播种产出合规记录、**不许伪造 avg_view_sec**、
风控时必须报错而不是静默写出空目录、slug 稳定。

## 2026-10-25 · F7 用真实榜单数据当同题材基线

发现一个洞：我们唯一的**真实数据源**（公开接口）给不出完播率所需的平均播放时长，
而完播率恰好是我先前默认的主指标 —— 等于主指标在真实数据上永远是 `-`。补救：换成**比值型指标 `interaction`**
（点赞+币+收藏+评论+分享）/ 播放。这是接口真能给的。

**新工具** `tools/seed_from_ranking.py`：从 `ranking/v2` 拉真实榜单，落成基线记录。
工具自己在输出里提醒：这是**别人的视频**的累计值，只能比比值型指标，不能比绝对播放量。

**daily_check 支持 `--metric`**：周表的指标列可在 completion / interaction / ctr 之间切换。

**真实数据实测**（2026-10-25 抓取，15 条真实榜单视频）：

```
$ python tools/seed_from_ranking.py --top 15 --cohort real-ranking --out _baseline-real
已写入 15 条真实基线到 _baseline-real（cohort=real-ranking，抓取时刻 2026-10-25T19:48:20+08:00）
提醒：这是别人的视频的累计值，只能比比值型指标，不能比绝对播放量。

$ python tools/validate_run.py _baseline-real
结果：15 份记录全部通过

$ python tools/cohort_check.py _baseline-real --cohort real-ranking --metric interaction
  样本不足：要看得出 30% 的退步需要 35 条，现在只有 15 条 —— 不判「无退步」。
判定：不可判定
本窗口可判定的最小退步：45%（n=15, sigma=0.5, alpha=0.05 单侧, power=0.80）
```

**这次实测最有价值的地方**：15 条真实数据跑出来的是「不可判定」而不是一个漂亮结论 —— 这正是设计意图。

测试：33 passed。

## 2026-10-25 · F6 把「记录」做便宜（针对 D2 第一条关停条件）

D2 写的第一条关停条件是「4 周内没人用它记录满 7 天 → 记录这个动作太重」。
这一轮就是为了反驳它：手写 JSONL 太贵，所以给一条命令。

**新工具** `tools/new_run.py`

- 先过选题准入卡；**不过就拒绝创建**（不是警告）——硬塞进去的记录会让一周的对照失效
- 落 `topic.pick`（带 cohort），给了 `--bvid` 就顺带落 `publish`
- 打印正确的下一步顺序：取数 → 校验 → 周表

**validator 新增 `--allow-incomplete`**

刚建的记录还没取数，严格模式会报 V9（缺 metrics）。加这个开关后 V9 降级为提示，
让人能在「还没发布」阶段就检查选题部分，而不会被一个必然失败的红吓回去。

**实测**

```
$ python tools/new_run.py --title "3 个把 Claude 用废的坏习惯" --cohort tutorial --who ... --date 2026-10-26 --dir _runs
已创建 _runs\2026-10-26-3-个把-Claude-用废的坏习惯（档位 daily）

$ python tools/new_run.py --title "随便聊聊" --dir _runs
拒绝创建：这条选题没过准入卡
  [A1] 三行不齐 / [A2] 没写素材耗时 / [A3] 不可证伪 / [A4] 说不出差异
```

测试：33 passed（新增 5 条）

## 2026-10-25 · F5 发布准备

- README 重写：一屏内先给 `status.py` 的 6/6 自检与「做不到」清单，再给真实 API 取数输出、周表输出、7 天不足看「退」的数字；显式声明不拿回放当卖点、不承诺播放量
- 新增 `LICENSE`（MIT）、`.gitignore`（排除 `_live/` `_demo/` `__pycache__`）
- 新增 6 条发布前自检测试：README 必须承认三条边界、不许出现「提升播放量」类承诺、提到的文件必须真实存在、**统计数字必须能在 ENGINEERING.md 里找到出处**

测试：28 passed。发布（建远端仓库）尚未执行，等用户确认。

## 2026-10-25 · F1/F2/F3 接真实数据

**新工具** `tools/fetch_stats.py`

- 走 B站公开接口 `x/web-interface/view?bvid=`，落地实测可用
- 落 `snapshot_at` 与 `hours_since_publish`；`at_hours` 明确标注为近似（接口只给累计值，没有「满 24 小时」这个时点）
- **接口不给的字段就不写**：`avg_view_sec` 缺失时直接不落该字段，不填 0 冒充 —— 因此这类记录算不了完播率，cohort 会自动跳过它们而不是算成 0

**validator 相应放宽**：`avg_view_sec` 从必填改为可选；`metrics` 仍要求 `at_hours` / `views` / `duration_sec`

**端到端实测**（真实 BVID `BV1GJ411x7h7`，2026-10-25 抓取）：

```
$ python tools/fetch_stats.py BV1GJ411x7h7 --run-dir _live/2026-10-24-live
已写入 _live\2026-10-24-live\events.jsonl
  播放 107681276 · 点赞 2963009 · 币 1287302 · 收藏 1558848 · 评论 238744
  发布到取数经过 59748.0 小时（at_hours 记为 72，这是近似而非精确 T+24h）

$ python tools/validate_run.py _live
PASS  2026-10-24-live
结果：1 份记录全部通过
```

**测试** 21 passed（新增 6 条，全部用录制好的 fixture，不依赖网络）