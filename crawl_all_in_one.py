# -*- coding: utf-8 -*-
import os, re, json, time, base64, urllib.request, urllib.parse
from datetime import datetime

# --- 深度提取配置 ---
# 搜索关键词列表：包含你上传脚本中的核心特征
KEYWORDS = [
    '"/api/v1/client/subscribe?token="',
    'sub?target=clash&url=',
    'data-link="https://'
]
TG_CHANNELS = ["v2rayfree", "clash_v2ray_free", "shareCentre", "v2ray_free_conf", "clash_subscription"]

def http_get(url, headers=None):
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.google.com/"
    }
    if headers: default_headers.update(headers)
    try:
        req = urllib.request.Request(url, headers=default_headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')
    except: return ""

def extract_all(text):
    """
    参考 wzdnzd 提取逻辑：
    1. 提取订阅 URL
    2. 提取单节点并尝试解码
    """
    subs, nodes = [], []
    # 订阅链接正则 (通用 + 专用接口)
    sub_pattern = r'https?://(?:[a-zA-Z0-9-]+\.)+[a-z]{2,}(?::\d+)?/(?:api/v1/client/subscribe\?token=[a-zA-Z0-9]{16,32}|link/[a-zA-Z0-9]+|s/[a-zA-Z0-9]{15,}|sub\?target=\w+&url=[^\s\'\"]+)'
    # 协议正则
    node_pattern = r'(?:vmess|trojan|ss|ssr|vless|hysteria2|tuic)://[a-zA-Z0-9:.?+=@%&#_\-/]{15,}'
    
    subs.extend(re.findall(sub_pattern, text, re.I))
    nodes.extend(re.findall(node_pattern, text, re.I))
    
    # Base64 深度探测 (很多订阅内容是整段 B64 编码的)
    try:
        # 匹配可能是 B64 的块
        b64_blocks = re.findall(r'[a-zA-Z0-9+/=]{50,}', text)
        for block in b64_blocks:
            try:
                decoded = base64.b64decode(block).decode('utf-8', errors='ignore')
                if any(p in decoded for p in ['vmess://', 'http']):
                    s, n = extract_all(decoded)
                    subs.extend(s); nodes.extend(n)
            except: pass
    except: pass
    return list(set(subs)), list(set(nodes))

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 启动强化抓取任务...")
    gh_token = os.environ.get("GH_TOKEN")
    detail = {"Google": 0, "Yandex": 0, "Telegram": 0, "GitHub": 0}
    all_s, all_n = [], []

    # 1. Google 深度搜索
    print("[+] 正在执行 Google Dorking...", end=" ", flush=True)
    for kw in KEYWORDS[:2]:
        url = f"https://www.google.com/search?q={urllib.parse.quote(kw)}&tbs=qdr:d" # 只搜24小时内更新
        s, n = extract_all(http_get(url))
        all_s.extend(s); all_n.extend(n); detail["Google"] += len(s)
        time.sleep(2)
    print("完成")

    # 2. Yandex
    print("[+] 正在请求 Yandex 接口...", end=" ", flush=True)
    url = f"https://yandex.com/search/?text={urllib.parse.quote(KEYWORDS[0])}"
    s, n = extract_all(http_get(url))
    all_s.extend(s); all_n.extend(n); detail["Yandex"] = len(s)
    print("完成")

    # 3. Telegram 频道扫描
    print("[+] 正在解析 Telegram 消息...", end=" ", flush=True)
    for c in TG_CHANNELS:
        content = http_get(f"https://t.me/s/{c}")
        s, n = extract_all(content)
        all_s.extend(s); all_n.extend(n); detail["Telegram"] += len(s)
    print("完成")

    # 4. GitHub API (最稳定的来源)
    if gh_token:
        print("[+] 正在通过 GitHub API 检索...", end=" ", flush=True)
        headers = {"Authorization": f"token {gh_token}", "Accept": "application/vnd.github.v3+json"}
        # 尝试搜索代码片段
        api_url = f"https://api.github.com/search/code?q={urllib.parse.quote(KEYWORDS[0])}&sort=indexed"
        try:
            items = json.loads(http_get(api_url, headers=headers)).get('items', [])[:20]
            for item in items:
                raw_url = item['html_url'].replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                s, n = extract_all(http_get(raw_url))
                all_s.extend(s); all_n.extend(n); detail["GitHub"] += len(s)
        except: pass
        print("完成")

    # 数据去重与白名单过滤 (排除常见的垃圾干扰项)
    final_subs = sorted(list(set([s for s in all_s if "127.0.0.1" not in s and "localhost" not in s])))
    final_nodes = sorted(list(set(all_n)))

    os.makedirs("results", exist_ok=True)
    with open("results/subscribes.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_subs))
    with open("results/nodes.txt", "w", encoding="utf-8") as f: f.write("\n".join(final_nodes))

    print("\n" + "="*40)
    print(f"{'来源渠道':<15} | {'新增订阅链接':<10}")
    print("-" * 40)
    for k, v in detail.items(): print(f"{k:<17} | {v:<10}")
    print("="*40)
    print(f"最终结果: 订阅 {len(final_subs)} / 独立节点 {len(final_nodes)}")

if __name__ == "__main__":
    main()
