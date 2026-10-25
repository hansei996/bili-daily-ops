# 取数的现实约束（实测记录）

> 2026-10-25 实测。这些不是猜测，是接口当场返回的 code。

| 端点 | 结果 | 结论 |
|---|---|---|
| `x/web-interface/view?bvid=` 单条 | `code=0` 可用 | **可以用**，这是我们的主通道 |
| `x/space/arc/search`（空间列表） | `code=-799` 请求过于频繁 | 不可用 |
| `x/space/wbi/arc/search`（带 WBI 签名） | `code=-352` 风控校验失败 | 不可用，签名正确也一样 |
| `x/web-interface/ranking/v2`（榜单） | 第一次 `code=0`，几分钟后 `-352` | 间歇可用，已做回退 |
| `x/web-interface/popular`（热门） | `code=0` | 相对稳，作为榜单的回退源 |

## 所以「枚举我的视频」这件事，我们不做

原因不是技术上做不到（WBI 签名已经实现了），是**不值得**：

- 空间接口的风控是针对**账号和 IP** 的，硬打会有把你自己的号打进去的风险；
- 你有更好的来源：**创作中心里本来就有完整的稿件列表**。

## 正确姿势：一次复制，之后按 BVID 取

```bash
# bvids.txt 里每行一个 BVID（可以整段粘贴，多余的字段会被忽略）
python tools/register_videos.py bvids.txt --cohort tutorial --out runs
```

工具会：按 BVID 逐条取数 → 落 `publish` + `metrics` 事件 → 打印每条的标题与播放。
已登记的会跳过，所以这个命令可以安全重复运行。

## 快照的诚实边界

单条接口给的是**抓取时刻的累计值**，不是「发布满 24 小时那一刻」。
所以我们落 `snapshot_at` 和 `hours_since_publish`，并在 `at_hours` 上标注它是近似。

**不要把这个数字当成「T+24h 数据」对外说。**
