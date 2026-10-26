#!/usr/bin/env python3
"""单源同步：把资源分享师 ZYFXS 最新的 v2ray 订阅文件原样同步为 nodes.txt。

只有一个源，不存在合并，也不过滤：
- 不去重、不按 remark 过滤、不按协议过滤——nodes.txt 就是当日文件的
  明文内容（一行一个节点），连 anytls 这类新协议也原样保留。
- 唯一做的三件事：
  1. 找到最新文件：UP 主频繁改名，不依赖文件名格式，按"含 zyfxs、
     非 Clash、提交时间最新、内容校验为订阅"自动挑选；
  2. base64 解码成明文（Karing 直接识别的格式）；
  3. 写入 nodes.txt。

用法: python sync.py
输出: nodes.txt（明文节点，Karing 订阅直接可用）

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

# 节点链接行：任意协议头 + "://"，不限制协议种类（vless/ss/trojan/
# hysteria2/anytls/vmess……一律保留，不过滤）
_LINK_PAT = re.compile(r"^[A-Za-z0-9+.\-]+://")


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
            continue  # Clash 订阅（*-c / *-C 结尾），不是 v2ray 通用格式
        cands.append(it)
    return cands


def decode_if_base64(data: bytes) -> str:
    """订阅文件可能是 base64 或明文：首行含 "://" 即为明文，否则解码。"""
    text = data.decode("utf-8", errors="ignore").strip()
    if not text:
        return text
    first = text.splitlines()[0].strip()
    if "://" in first:
        return text
    try:  # 尝试 base64 解码（自动补齐 padding）
        padded = text + "=" * (-len(text) % 4)
        return base64.b64decode(padded).decode("utf-8", errors="ignore")
    except Exception:
        return text


def _looks_like_subscription(data: bytes) -> bool:
    """内容校验：解码后是否包含节点链接行（不限协议）。"""
    for line in decode_if_base64(data).splitlines():
        if _LINK_PAT.match(line.strip()):
            return True
    return False


def zyfxs_latest_url() -> str:
    """从 GitHub API 取 ZYFXS001 仓库目录，挑出最新的 v2ray 订阅文件。

    不依赖文件名格式：筛选含 zyfxs 的文件、排除 Clash 订阅与代码
    文档，按提交时间倒序逐个下载做内容校验，第一个确认的即采用。
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
        if data and len(data) > 100 and _looks_like_subscription(data):
            print(f"[信息] ZYFXS 选用最新文件: {it['name']}", file=sys.stderr)
            return url
        print(f"[警告] ZYFXS 候选 {it['name']} 内容不是订阅，跳过",
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


def main() -> None:
    raw, used = fetch_first([zyfxs_latest_url()])
    # 原样同步：只去掉空行，不去重、不过滤、不改写任何节点
    nodes = [l.strip() for l in decode_if_base64(raw).splitlines()
             if l.strip()]
    if not nodes:
        print("未取到任何节点，拒绝写入空文件", file=sys.stderr)
        sys.exit(2)
    with open("nodes.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(nodes) + "\n")
    print(f"完成：{used} -> nodes.txt，共 {len(nodes)} 个节点")


if __name__ == "__main__":
    main()
