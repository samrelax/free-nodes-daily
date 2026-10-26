#!/usr/bin/env python3
"""合并资源分享师 ZYFXS 每日更新的 v2ray 节点订阅，去重后输出合并订阅文件。

用法: python merge.py
输出: merged.txt（base64 订阅，Karing/v2ray 通用格式）
      merged-raw.txt（明文节点，方便检查）

注意：只合并 v2ray 通用格式（base64 节点串）。Clash YAML 订阅
（如 youtube@ZYFXS-18c）不参与合并，请在 Karing 里另加。

文件发现不依赖文件名格式：UP 主频繁改名（如 15V-youtube@ZYFXS、
youtube@ZYFXS--12v、youtube@ZYFXS-18v），脚本按"含 zyfxs、
非 Clash、提交时间最新、内容校验为 v2ray 订阅"自动挑选。

过滤：中国大陆节点会被去掉（按 remark 识别，港澳台保留）。

高频轮询（Actions 每 30 分钟跑一次）时，GitHub API 调用走环境变量
GITHUB_TOKEN（Actions 内置 token，无需手动配置），避免未认证
60 次/小时限流；没有 token 时退回未认证调用。
"""
import base64
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ZYFXS_REPO = "ZYFXS/ZYFXS001"
UA = {"User-Agent": "Mozilla/5.0"}

SCHEMES = (
    "vmess://", "vless://", "trojan://", "ss://", "ssr://",
    "hysteria2://", "hysteria://", "tuic://", "socks5://",
)


def fetch(url: str, timeout: int = 30) -> bytes:
    headers = dict(UA)
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
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


def _zyfxs_candidate_files(items):
    """从仓库目录列表中挑出疑似 v2ray 订阅文件的候选。

    不依赖具体文件名格式（UP 主频繁改名）：文件名含 zyfxs、
    不是代码/文档、不是 Clash 订阅（以 c/C 结尾）的即纳入。
    """
    cands = []
    for it in items:
        if not isinstance(it, dict) or it.get("type") != "file":
            continue
        name = it.get("name", "")
        low = name.lower()
        if "zyfxs" not in low:
            continue
        if low.endswith((".js", ".md", ".txt", ".json", ".yml", ".yaml",
                         ".png", ".jpg", ".jpeg")):
            continue
        if low.endswith("c"):
            continue  # Clash 订阅（*-c / *-C 结尾），不参与合并
        cands.append(it)
    return cands


def _looks_like_v2ray_subscription(data: bytes) -> bool:
    """内容校验：解码后是否包含 v2ray 节点链接行。"""
    for line in decode_if_base64(data).splitlines():
        if line.strip().startswith(SCHEMES):
            return True
    return False


def zyfxs_latest_url() -> str:
    """从 GitHub API 取 ZYFXS001 仓库目录，挑出最新的 v2ray 订阅文件。

    不依赖文件名格式：筛选含 zyfxs 的文件、排除 Clash 订阅与代码
    文档，按提交时间倒序逐个下载做内容校验，第一个确认为 v2ray
    订阅的即采用。
    """
    try:
        data = fetch(f"https://api.github.com/repos/{ZYFXS_REPO}/contents/",
                     timeout=20)
        items = json.loads(data.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return zyfxs_fallback_url(e)

    cands = _zyfxs_candidate_files(items)
    if not cands:
        return zyfxs_fallback_url("目录中没有找到疑似 v2ray 订阅文件")

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
    for it in cands:
        url = it.get("download_url")
        if not url:
            continue
        try:
            data = fetch(url, timeout=30)
        except Exception as e:  # noqa: BLE001
            print(f"[警告] ZYFXS 候选 {it['name']} 下载失败: {e}",
                  file=sys.stderr)
            continue
        if data and len(data) > 100 and _looks_like_v2ray_subscription(data):
            print(f"[信息] ZYFXS 选用最新文件: {it['name']}", file=sys.stderr)
            return url
        print(f"[警告] ZYFXS 候选 {it['name']} 内容不是 v2ray 订阅，跳过",
              file=sys.stderr)
    return zyfxs_fallback_url("所有候选文件内容校验均未通过")


def zyfxs_fallback_url(reason) -> str:
    """API 不可用时，按北京时间今天/昨天日期拼文件名。
    新、旧两种命名格式都试一遍（文件名会不定期改版）。"""
    print(f"[警告] ZYFXS 自动解析失败({reason})，改用日期拼凑",
          file=sys.stderr)
    today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))).date()
    tried = set()
    for d in (today, today - datetime.timedelta(days=1)):
        # 已知历史格式全部试一遍（含 V/v 大小写，raw URL 区分大小写）
        names = []
        for day in (d.day,):
            names += [f"{day}V-youtube@ZYFXS", f"{day}v-youtube@ZYFXS",
                      f"{day}V--youtube@ZYFXS", f"{day}v--youtube@ZYFXS",
                      f"youtube@ZYFXS-{day}V", f"youtube@ZYFXS-{day}v",
                      f"youtube@ZYFXS--{day}V", f"youtube@ZYFXS--{day}v",
                      f"youtube@ZYFXS---{day}V", f"youtube@ZYFXS---{day}v",
                      f"{day}-v-youtube@ZYFXS"]
        for name in names:
            if name in tried:
                continue
            tried.add(name)
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


def source_urls():
    """返回 (名称, 候选地址列表)。2026-10-19 起只保留资源分享师单源
    （其余源速度慢，已按用户要求移除）。"""
    return [
        ("资源分享师 ZYFXS（日更，自动取最新）", [zyfxs_latest_url()]),
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

# 2026-10-26 注：新版 .github/workflows/daily-merge.yml（每 30 分钟轮询）
# 已在"提交更新"步骤加 git pull --rebase 并用 concurrency 串行化运行，
# 2026-10-19 的并发推送冲突问题随之解决（仍需用户在 GitHub 网页端粘贴
# 新版 workflow 文件后生效，App token 无权写 .github/workflows，API 推送 403）。
