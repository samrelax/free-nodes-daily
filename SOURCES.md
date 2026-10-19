# 节点渠道表（SOURCES.md）

GitHub Actions 每天北京时间 14:00 自动合并使用的节点源。`merge.py` 按此表抓取订阅，去重 + 过滤中国大陆节点（港澳台保留）后输出 `merged.txt`（base64 通用订阅，Karing / v2ray 通用）。

固定订阅地址（Karing 只需添加一次，之后每天自动更新）：
`https://raw.githubusercontent.com/samrelax/free-nodes-daily/main/nodes.txt`

## 在用渠道（2026-10-19 起：仅保留资源分享师单源）

| 渠道 | 订阅地址 | 更新频率 | 格式 | 备注 |
|---|---|---|---|---|
| 资源分享师 @ZYFXS（YouTube 日更视频） | 自动识别当日文件（不依赖文件名格式：按含 zyfxs、非 Clash、提交时间最新、内容校验为 v2ray 订阅自动挑选） | 每日 | base64 v2ray 通用 | 文件名频繁改版已不再是障碍；2026-10-19 重写发现逻辑 |

## 已移除 / 未纳入

| 渠道 | 状态 |
|---|---|
| free18/v2ray、junjun266/FreeProxyGo、Ruk1ng001/freeSub、Alirewa/V2ray-Configs、mahdibland/V2RayAggregator | 2026-10-19 用户要求移除：速度慢，只保留资源分享师单源 |
| bg0da/Free-Node | 2026-09-05 起停更（仓库更名为 flik6/Free-Node），raw 链接返回空内容，已从合并源移除 |
| 爱分享的小妾（YouTube 7x24 直播） | 自 2026-10-09 起未获取到可用免费订阅链接（博客打不开、直播实际离线），暂不纳入合并 |

## 维护说明

- 新增渠道：验证订阅 URL 稳定、内容非空、节点真实可用后，按 `("名称", ["地址1", "地址2(备用)"])` 格式追加到 `merge.py` 的 `source_urls()`，并在本表登记。
- 已停更的源请及时从 `merge.py` 移除，并在上表留一行记录。
- 只合并 v2ray 通用格式（base64 或明文节点行）；Clash YAML 订阅不参与合并。
