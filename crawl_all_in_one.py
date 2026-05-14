# -*- coding: utf-8 -*-
import os
import re
import json
import time
import base64
import urllib.request
import urllib.parse
from datetime import datetime

# --- 核心配置 (参考 wzdnzd 逻辑) ---
SEARCH_KEYWORD = '"/api/v1/client/subscribe?token="'
# 增加一些变体关键词提高命中率
SEARCH_VARIANTS = ['"/api/v1/client/subscribe?token="', 'sub?target=clash', 'vmess://', 'ssr://']
TG_CHANNELS = ["v2rayfree", "clash_v2ray_free", "shareCentre", "v2ray_free_conf", "free520v2ray"]

def http_get(url, headers=None):
    # 模拟真实浏览器，防止被 Google/Yandex 直接拦截
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    if headers: default_headers.update(headers)
    try:
        req = urllib.request.Request(url, headers=default_headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        # print(f"Error fetching {url[:50]}: {e}") # 调试用
        return ""

def extract_content(content):
    """参考 wzdnzd 的提取逻辑，同时支持订阅链接和节点协议"""
    # 1. 提取订阅链接 (V2board / SSpanel 等)
    sub_regex = r'https?://[^\s\"\'<>]+(?:/api/v1/client/subscribe\?token=[a-zA-Z0-9]{16,32}|/link/[a-zA-Z0-9?=&]+|/s/[a-zA-Z0-9]{15,})'
    # 2. 提取单节点协议
    proto_regex = r'(?:vmess|trojan|ss|ssr|vless|hysteria2|tuic)://[a-zA-Z0-9:.?+=@%&#_\-/]{10,}'
    
    subs = re.findall(sub_regex, content, re.I)
    nodes = re.findall(proto_regex, content, re.I)
    
    # 尝试 Base64 解码提取 (处理某些网页加密内容)
    try:
        if len(content) > 100 and not content.startswith("http"):
            decoded = base64.b64decode(content).decode('utf-8', errors='ignore')
            s, n = extract_content(decoded)
            subs.extend(s)
            nodes.extend(n)
    except:
        pass
        
    return list(set(subs)), list(set(nodes))

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始执行全能抓取任务...")
    gh_token = os.environ.get("GH_TOKEN")
    stats = {"Google": 0, "Yandex": 0, "Telegram": 0, "GitHub": 0}
    
    all_subs, all_nodes = [], []

    # 1. Google (加入延时防止被封)
    print("[+] 搜索 Google...", end=" ", flush=True)
    for kw in SEARCH_VARIANTS[:1]: # 默认只用第一个核心词
        for start in [0, 10]:
            url = f"https://www.google.com/search?q={urllib.parse.quote(kw)}&start={start}"
            content = http_get(url)
            s, n = extract_content(content)
            all_subs.extend(s); all_nodes.extend(n)
            stats["Google"] += len(s)
            time.sleep(3)
    print(f"完成")

    # 2. Yandex
    print("[+] 搜索 Yandex...", end=" ", flush=True)
    url = f"https://yandex.com/search/?text={urllib.parse.quote(SEARCH_KEYWORD)}"
    content = http_get(url)
    s, n = extract_content(content)
    all_subs.extend(s); all_nodes.extend(n)
    stats["Yandex"] = len(s)
    print(f"完成")

    # 3. Telegram (网页版解析)
    print("[+] 抓取 Telegram...", end=" ", flush=True)
    for channel in TG_CHANNELS:
        content = http_get(f"https://t.me/s/{channel}")
        s, n = extract_content(content)
        all_subs.extend(s); all_nodes.extend(n)
        stats["Telegram"] += len(s)
    print(f"完成")

    # 4. GitHub API
    if gh_token:
        print("[+] 搜索 GitHub...", end=" ", flush=True)
        headers = {"Authorization": f"token {gh_token}", "Accept": "application/vnd.github.v3+json"}
        # 搜索最近更新的代码
        api_url = f"https://api.github.com/search/code?q={urllib.parse.quote(SEARCH_KEYWORD)}&sort=indexed"
        res = http_get(api_url, headers=headers)
        try:
            items = json.loads(res).get('items', [])[:15]
            for item in items:
                raw_url = item['html_url'].replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                content = http_get(raw_url)
                s, n = extract_content(content)
                all_subs.extend(s); all_nodes.extend(n)
                stats["GitHub"] += len(s)
        except: pass
        print(f"完成")

    # 数据去重过滤
    unique_subs = sorted(list(set(all_subs)))
    unique_nodes = sorted(list(set(all_nodes)))

    # 保存
    os.makedirs("results", exist_ok=True)
    with open("results/subscribes.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(unique_subs))
    with open("results/nodes.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(unique_nodes))

    print("\n" + "="*40)
    print(f"{'来源':<15} | {'发现订阅数':<10}")
    print("-" * 40)
    for k, v in stats.items():
        print(f"{k:<17} | {v:<10}")
    print("="*40)
    print(f"总计去重: 订阅 {len(unique_subs)} / 节点 {len(unique_nodes)}")

if __name__ == "__main__":
    main()
