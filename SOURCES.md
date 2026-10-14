# 节点渠道表（SOURCES.md）

GitHub Actions 每天北京时间 14:00 自动合并使用的节点源。`merge.py` 按此表抓取订阅，去重 + 过滤中国大陆节点（港澳台保留）后输出 `merged.txt`（base64 通用订阅，Karing / v2ray 通用）。

固定订阅地址（Karing 只需添加一次，之后每天自动更新）：
`https://raw.githubusercontent.com/samrelax/free-nodes-daily/main/nodes.txt`

## 在用渠道

| 渠道 | 订阅地址 | 更新频率 | 格式 | 备注 |
|---|---|---|---|---|
| 资源分享师 @ZYFXS（YouTube 日更视频） | 自动识别当日文件（`youtube@ZYFXS--{日}v`，双横线及以上；旧格式 `{日}-v-youtube@ZYFXS` 回退） | 每日 | base64 v2ray 通用 | 文件名会不定期改版，merge.py 按提交时间自动选最新，兼容新旧两种命名 |
| free18/v2ray（GitHub） | `https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/v.txt` | 每日 | base64 v2ray 通用 | pan635/v2ray（VV科技）同源；另有 Clash Meta 版 `c.yaml`（不参与合并，Karing 可另加） |
| junjun266/FreeProxyGo（GitHub） | `https://sub.proxygo.org/v2ray.php?key=…`（key 每日轮换，以其 README 当天为准） | 每 6 小时 | base64 v2ray 通用 | merge.py 自动从 README 读取当日 key；2026-10-12 起 key 改为 README 动态读取 |
| Ruk1ng001/freeSub（GitHub） | `https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/v2ray` | 每日 | base64 v2ray 通用 | 2026-10-12 首次发现并验证有效；2026-10-13 复验 HTTP 200，base64 解码出 82 个有效节点（vmess 55 / ss 14 / vless 11 / trojan 2），正式纳入合并 |

## 已移除 / 未纳入

| 渠道 | 状态 |
|---|---|
| bg0da/Free-Node | 2026-09-05 起停更（仓库更名为 flik6/Free-Node），raw 链接返回空内容，已从合并源移除 |
| 爱分享的小妾（YouTube 7x24 直播） | 自 2026-10-09 起未获取到可用免费订阅链接（博客打不开、直播实际离线），暂不纳入合并 |

## 维护说明

- 新增渠道：验证订阅 URL 稳定、内容非空、节点真实可用后，按 `("名称", ["地址1", "地址2(备用)"])` 格式追加到 `merge.py` 的 `source_urls()`，并在本表登记。
- 已停更的源请及时从 `merge.py` 移除，并在上表留一行记录。
- 只合并 v2ray 通用格式（base64 或明文节点行）；Clash YAML 订阅不参与合并。
