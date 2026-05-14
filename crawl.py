# -*- coding: utf-8 -*-
import os
import re
import json
import time
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# --- 配置区 (也可以通过环境变量传入) ---
SEARCH_KEYWORD = '"/api/v1/client/subscribe?token="'
TG_CHANNELS = ["v2rayfree", "clash_v2ray_free", "shareCentre"]  # 示例频道
EXCLUDE_DOMAINS = "github.com|google.com|yandex.com|telegram.org"

def http_get(url, headers=None, params=None):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if headers:
        default_headers.update(headers)
    
    try:
        req = urllib.request.Request(url, headers=default_headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[!] 请求失败 {url}: {e}")
        return ""

def extract_links(content):
    """提取订阅链接和通用代理协议"""
    # 匹配各类订阅格式
    sub_regex = r'https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z0-9-]+(?::\d+)?/(?:api/v1/client/subscribe\?token=[a-zA-Z0-9]{16,32}|link/[a-zA-Z0-9]+\?(?:sub|clash)=\d|s/[a-zA-Z0-9]{32})'
    # 匹配节点协议
    proto_regex = r'(?:vmess|trojan|ss|ssr|vless|hysteria2|tuic)://[a-zA-Z0-9:.?+=@%&#_\-/]{10,}'
    
    links = re.findall(sub_regex, content, re.I)
    nodes = re.findall(proto_regex, content, re.I)
    return list(set(links)), list(set(nodes))

def crawl_google(limit=50):
    print("[+] 正在搜索 Google...")
    results = []
    query = urllib.parse.quote(SEARCH_KEYWORD)
    for start in range(0, limit, 10):
        url = f"https://www.google.com/search?q={query}&start={start}&tbs=qdr:d7"
        content = http_get(url)
        links, _ = extract_links(content)
        results.extend(links)
        time.sleep(2)
    return results

def crawl_yandex(pages=3):
    print("[+] 正在搜索 Yandex...")
    results = []
    query = urllib.parse.quote(SEARCH_KEYWORD)
    for p in range(pages):
        url = f"https://yandex.com/search/?text={query}&p={p}"
        content = http_get(url)
        links, _ = extract_links(content)
        results.extend(links)
        time.sleep(2)
    return results

def crawl_telegram():
    print("[+] 正在抓取 Telegram 频道...")
    all_links, all_nodes = [], []
    for channel in TG_CHANNELS:
        url = f"https://t.me/s/{channel}"
        content = http_get(url)
        links, nodes = extract_links(content)
        all_links.extend(links)
        all_nodes.extend(nodes)
    return all_links, all_nodes

def crawl_github(token):
    if not token:
        print("[!] 跳过 GitHub: 无 GH_TOKEN")
        return []
    print("[+] 正在抓取 GitHub Code...")
    results = []
    query = urllib.parse.quote(SEARCH_KEYWORD)
    url = f"https://api.github.com/search/code?q={query}&sort=indexed&order=desc"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    content = http_get(url, headers=headers)
    try:
        data = json.loads(content)
        for item in data.get('items', []):
            raw_url = item.get('html_url', '').replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            file_content = http_get(raw_url)
            links, _ = extract_links(file_content)
            results.extend(links)
    except:
        pass
    return results

def main():
    start_time = datetime.now()
    gh_token = os.environ.get("GH_TOKEN")
    
    found_links = []
    found_nodes = []

    # 运行各个爬虫
    found_links.extend(crawl_google())
    found_links.extend(crawl_yandex())
    links, nodes = crawl_telegram()
    found_links.extend(links)
    found_nodes.extend(nodes)
    found_links.extend(crawl_github(gh_token))

    # 去重与过滤
    unique_links = sorted(list(set([l for l in found_links if not re.search(EXCLUDE_DOMAINS, l)])))
    unique_nodes = sorted(list(set(found_nodes)))

    # 保存结果
    os.makedirs("results", exist_ok=True)
    
    with open("results/subscribes.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(unique_links))
    
    with open("results/nodes.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(unique_nodes))

    print(f"\n[√] 抓取完成! 耗时: {datetime.now() - start_time}")
    print(f"[i] 订阅链接: {len(unique_links)} | 独立节点: {len(unique_nodes)}")

if __name__ == "__main__":
    main()
