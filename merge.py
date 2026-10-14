#!/usr/bin/env python3
"""合并多个 v2ray/base64 格式的节点订阅，去重后输出合并订阅文件。

用法: python merge.py
输出: merged.txt（base64 订阅，Karing/v2ray 通用格式）
      merged-raw.txt（明文节点，方便检查）

注意：只合并 v2ray 通用格式（base64 节点串）。Clash YAML 订阅
（如 ZYFXS 的 youtube@ZYFXS---{日}c / 旧 *-c-youtube@ZYFXS）不参与合并，
请在 Karing 里另加。

过滤：中国大陆节点会被去掉（按 remark 识别，港澳台保留）。
"""
import base64
import datetime
import json
import re
import sys
import urllib.parse
import urllib.request

ZYFXS_REPO = "ZYFXS/ZYFXS001"
# ZYFXS 的 v2ray 文件名会不定期改版，已知格式：
#   2026-10-13 起：{日}v--youtube@ZYFXS（日期+v 前缀） 如 13v--youtube@ZYFXS
#   2026-10-12 起：youtube@ZYFXS--{日}v（双横线）     如 youtube@ZYFXS--12v
#   2026-10-10 起：youtube@ZYFXS---{日}v（三横线）    如 youtube@ZYFXS---10v
#   旧格式：{日}-v-youtube@ZYFXS                       如 9-v-youtube@ZYFXS
ZYFXS_NAME_PATTERNS = (
    r"youtube@ZYFXS-{2,}(\d+)v",   # 双横线及以上，兼容未来再改版
    r"(\d+)v-{2,}youtube@ZYFXS",   # 2026-10-13 起：日期+v 前缀
    r"(\d+)-v-youtube@ZYFXS",
)
UA = {"User-Agent": "Mozilla/5.0"}

SCHEMES = (
    "vmess://", "vless://", "trojan://", "ss://", "ssr://",
    "hysteria2://", "hysteria://", "tuic://", "socks5://",
)


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_first(urls, timeout=30):
    """按顺序尝试多个候选地址，返回第一个成功抓到的内容。"""
    last_err = None
    for url in urls:
        try:
            data = fetch(url, timeout)
            if data and len(data) > 100:
                return data, url
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"全部候选地址失败: {urls} ({last_err})")


def zyfxs_latest_url() -> str:
    """从 GitHub API 取 ZYFXS001 仓库目录，按提交时间选出最新的
    v2ray 文件（文件名里的日期会天天变，格式也可能改版）。"""
    try:
        data = fetch(f"https://api.github.com/repos/{ZYFXS_REPO}/contents/",
                     timeout=20)
        items = json.loads(data.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return zyfxs_fallback_url(e)

    cands = [it for it in items
             if isinstance(it, dict)
             and any(re.fullmatch(p, it.get("name", ""))
                     for p in ZYFXS_NAME_PATTERNS)]
    if not cands:
        return zyfxs_fallback_url("目录中没有找到匹配的 v2ray 文件")

    def commit_date(item):
        try:
            path = urllib.parse.quote(item["path"], safe="")
            d = fetch(
                f"https://api.github.com/repos/{ZYFXS_REPO}/commits"
                f"?path={path}&per_page=1", timeout=20)
            commits = json.loads(d.decode("utf-8"))
            return commits[0]["commit"]["committer"]["date"]
        except Exception:  # noqa: BLE001
            return ""

    cands.sort(key=commit_date, reverse=True)
    best = cands[0]
    url = best.get("download_url")
    if url:
        print(f"[信息] ZYFXS 选用最新文件: {best['name']}", file=sys.stderr)
        return url
    return zyfxs_fallback_url("API 未返回 download_url")


def zyfxs_fallback_url(reason) -> str:
    """API 不可用时，按北京时间今天/昨天日期拼文件名。
    新、旧两种命名格式都试一遍（文件名会不定期改版）。"""
    print(f"[警告] ZYFXS 自动解析失败({reason})，改用日期拼凑",
          file=sys.stderr)
    today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))).date()
    for d in (today, today - datetime.timedelta(days=1)):
        names = [f"{d.day}v--youtube@ZYFXS",       # 2026-10-13 起格式
                 f"youtube@ZYFXS---{d.day}v",      # 2026-10-12 格式
                 f"{d.day}-v-youtube@ZYFXS"]        # 旧格式
        for name in names:
            url = ("https://raw.githubusercontent.com/ZYFXS/ZYFXS001/"
                   f"refs/heads/main/{urllib.parse.quote(name, safe='')}")
            try:
                data = fetch(url, timeout=20)
                if data and len(data) > 100:
                    print(f"[信息] ZYFXS 回退选用: {name}", file=sys.stderr)
                    return url
            except Exception:  # noqa: BLE001
                continue
    raise RuntimeError("ZYFXS 自动解析与日期回退全部失败")


def proxygo_latest_url() -> str:
    """FreeProxyGo 的订阅 key 每天轮换（写死会很快失效）。
    从其 GitHub README 里抓当前有效的 key，抓不到就回退到最近
    已知可用的 key 列表。"""
    try:
        data = fetch(
            "https://raw.githubusercontent.com/junjun266/FreeProxyGo/main/README.md",
            timeout=20)
        keys = re.findall(r"sub\.proxygo\.org/v2ray\.php\?key=([a-f0-9]+)",
                          data.decode("utf-8", errors="ignore"))
        if keys:
            print(f"[信息] FreeProxyGo 当前 key: {keys[0]}", file=sys.stderr)
            return f"https://sub.proxygo.org/v2ray.php?key={keys[0]}"
        print("[警告] README 里未找到 FreeProxyGo key，用已知 key 回退",
              file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[警告] 读取 FreeProxyGo README 失败({e})，用已知 key 回退",
              file=sys.stderr)
    # 最近已知可用的 key（key 会轮换，这里只作应急回退）
    return "https://sub.proxygo.org/v2ray.php?key=b39cc8182b56365ce019a4df250f0714"


def source_urls():
    """返回 (名称, 候选地址列表)。"""
    return [
        ("资源分享师 ZYFXS（日更，自动取最新）", [zyfxs_latest_url()]),
        ("free18/v2ray 通用订阅", [
            "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/v.txt",
            "https://ghfast.top/https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/v.txt",
        ]),
        ("FreeProxyGo v2ray（key 每日轮换，自动读取）", [proxygo_latest_url()]),
        ("Ruk1ng001/freeSub（GitHub 每日更新）", [
            "https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/v2ray",
        ]),
        # 想加更多源？按 ("名称", ["地址1", "地址2(备用)"]) 格式追加。
        # 必须是 base64 或明文的 v2ray 通用订阅；已停更的源请及时移除。
    ]


def decode_if_base64(data: bytes) -> str:
    text = data.decode("utf-8", errors="ignore").strip()
    if any(text.startswith(s) for s in SCHEMES):
        return text  # 已经是明文节点行
    try:  # 尝试 base64 解码（自动补齐 padding）
        padded = text + "=" * (-len(text) % 4)
        return base64.b64decode(padded).decode("utf-8", errors="ignore")
    except Exception:
        return text


# 港澳台标识：含这些的一律保留，不视为大陆节点
_KEEP_PAT = re.compile(
    r"香港|澳门|台灣|台湾|Hong\s?Kong|Macau|Macao|Taiwan"
    r"|(?<![A-Za-z])HK(?![A-Za-z])|(?<![A-Za-z])TW(?![A-Za-z])"
    r"|(?<![A-Za-z])MO(?![A-Za-z])|🇭🇰|🇲🇴|🇹🇼",
    re.I,
)
# 大陆标识：中国（不含中国香港/台湾/澳门）、大陆、🇨🇳、China、独立 CN
_CN_PAT = re.compile(
    r"🇨🇳|大陆|中国(?!香港|台湾|澳门)"
    r"|(?<![A-Za-z])China(?![A-Za-z])|(?<![A-Za-z])CN(?![A-Za-z])",
    re.I,
)


def node_remark(line: str) -> str:
    """提取节点链接的 remark（# 后面的名称，URL 解码）。"""
    try:
        scheme, rest = line.split("://", 1)
        if "#" in rest:
            return urllib.parse.unquote(rest.split("#", 1)[1])
        if scheme == "vmess":
            padded = rest + "=" * (-len(rest) % 4)
            d = json.loads(base64.b64decode(padded).decode("utf-8", errors="ignore"))
            return d.get("ps", "")
    except Exception:  # noqa: BLE001
        pass
    return ""


def is_mainland_cn(line: str) -> bool:
    """按 remark 判断是否为中国大陆节点（港澳台除外）。无 remark 的不误判。"""
    r = node_remark(line)
    if not r:
        return False
    if _KEEP_PAT.search(r):
        return False
    return bool(_CN_PAT.search(r))


def main() -> None:
    seen, nodes = set(), []
    total = 0
    for name, urls in source_urls():
        try:
            raw, used = fetch_first(urls)
        except Exception as e:  # noqa: BLE001
            print(f"[跳过] {name} 获取失败: {e}", file=sys.stderr)
            continue
        before = len(nodes)
        for line in decode_if_base64(raw).splitlines():
            line = line.strip()
            if line.startswith(SCHEMES) and line not in seen:
                seen.add(line)
                nodes.append(line)
        print(f"[OK] {name}: +{len(nodes) - before} 个 (累计 {len(nodes)})")
        total += 1

    # 过滤中国大陆节点（用户要求，港澳台保留）
    dropped = sum(1 for l in nodes if is_mainland_cn(l))
    nodes = [l for l in nodes if not is_mainland_cn(l)]
    if dropped:
        print(f"[过滤] 去掉中国大陆节点 {dropped} 个，剩余 {len(nodes)} 个")

    merged = "\n".join(nodes)
    with open("merged.txt", "w", encoding="utf-8") as f:
        f.write(base64.b64encode(merged.encode("utf-8")).decode())
    with open("merged-raw.txt", "w", encoding="utf-8") as f:
        f.write(merged)
    print(f"完成：{total} 个源可用，共 {len(nodes)} 个节点 -> merged.txt")
    if not nodes:
        sys.exit(2)


if __name__ == "__main__":
    main()
