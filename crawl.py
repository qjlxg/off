# -*- coding: utf-8 -*-
import os
import re
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime

# --- 配置区 ---
SEARCH_KEYWORD = '"/api/v1/client/subscribe?token="'
TG_CHANNELS = ["v2rayfree", "clash_v2ray_free", "shareCentre", "v2ray_free_conf"]
EXCLUDE_DOMAINS = "github.com|google.com|yandex.com|telegram.org|twitter.com"

def http_get(url, headers=None):
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if headers: default_headers.update(headers)
    try:
        req = urllib.request.Request(url, headers=default_headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')
    except:
        return ""

def extract_links(content):
    sub_regex = r'https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z0-9-]+(?::\d+)?/(?:api/v1/client/subscribe\?token=[a-zA-Z0-9]{16,32}|link/[a-zA-Z0-9]+\?(?:sub|clash)=\d|s/[a-zA-Z0-9]{32})'
    proto_regex = r'(?:vmess|trojan|ss|ssr|vless|hysteria2|tuic)://[a-zA-Z0-9:.?+=@%&#_\-/]{10,}'
    links = re.findall(sub_regex, content, re.I)
    nodes = re.findall(proto_regex, content, re.I)
    return list(set(links)), list(set(nodes))

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 任务启动...")
    gh_token = os.environ.get("GH_TOKEN")
    
    # 统计字典
    stats = {
        "Google": {"links": 0, "nodes": 0},
        "Yandex": {"links": 0, "nodes": 0},
        "Telegram": {"links": 0, "nodes": 0},
        "GitHub": {"links": 0, "nodes": 0}
    }
    
    all_links = []
    all_nodes = []

    # 1. Google
    print("[+] 搜索 Google...", end=" ", flush=True)
    g_links = []
    for start in range(0, 30, 10): # 抓取前3页
        content = http_get(f"https://www.google.com/search?q={urllib.parse.quote(SEARCH_KEYWORD)}&start={start}&tbs=qdr:d7")
        l, _ = extract_links(content)
        g_links.extend(l)
    stats["Google"]["links"] = len(set(g_links))
    all_links.extend(g_links)
    print(f"发现 {stats['Google']['links']} 条链接")

    # 2. Yandex
    print("[+] 搜索 Yandex...", end=" ", flush=True)
    y_links = []
    for p in range(2):
        content = http_get(f"https://yandex.com/search/?text={urllib.parse.quote(SEARCH_KEYWORD)}&p={p}")
        l, _ = extract_links(content)
        y_links.extend(l)
    stats["Yandex"]["links"] = len(set(y_links))
    all_links.extend(y_links)
    print(f"发现 {stats['Yandex']['links']} 条链接")

    # 3. Telegram
    print("[+] 抓取 Telegram...", end=" ", flush=True)
    tg_links, tg_nodes = [], []
    for channel in TG_CHANNELS:
        content = http_get(f"https://t.me/s/{channel}")
        l, n = extract_links(content)
        tg_links.extend(l)
        tg_nodes.extend(n)
    stats["Telegram"]["links"] = len(set(tg_links))
    stats["Telegram"]["nodes"] = len(set(tg_nodes))
    all_links.extend(tg_links)
    all_nodes.extend(tg_nodes)
    print(f"发现 {stats['Telegram']['links']} 链接 / {stats['Telegram']['nodes']} 节点")

    # 4. GitHub
    if gh_token:
        print("[+] 搜索 GitHub...", end=" ", flush=True)
        git_links = []
        headers = {"Authorization": f"token {gh_token}", "Accept": "application/vnd.github.v3+json"}
        content = http_get(f"https://api.github.com/search/code?q={urllib.parse.quote(SEARCH_KEYWORD)}&sort=indexed", headers=headers)
        try:
            items = json.loads(content).get('items', [])[:10] # 取前10个结果
            for item in items:
                raw_url = item['html_url'].replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                file_content = http_get(raw_url)
                l, _ = extract_links(file_content)
                git_links.extend(l)
        except: pass
        stats["GitHub"]["links"] = len(set(git_links))
        all_links.extend(git_links)
        print(f"发现 {stats['GitHub']['links']} 条链接")

    # 数据汇总与去重
    unique_links = sorted(list(set([l for l in all_links if not re.search(EXCLUDE_DOMAINS, l)])))
    unique_nodes = sorted(list(set(all_nodes)))

    # 保存结果
    os.makedirs("results", exist_ok=True)
    with open("results/subscribes.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(unique_links))
    with open("results/nodes.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(unique_nodes))

    # 打印最终明细表
    print("\n" + "="*30)
    print(f"{'来源渠道':<12} | {'链接数':<6} | {'节点数':<6}")
    print("-" * 30)
    for src, data in stats.items():
        print(f"{src:<14} | {data['links']:<8} | {data['nodes']:<8}")
    print("="*30)
    print(f"总计去重后: 订阅 {len(unique_links)} / 节点 {len(unique_nodes)}")

if __name__ == "__main__":
    main()
