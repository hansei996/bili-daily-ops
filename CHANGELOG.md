# 变更记录

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