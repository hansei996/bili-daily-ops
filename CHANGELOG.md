# 变更记录

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
