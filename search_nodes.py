import os
import re
import base64
import requests
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

# 配置
GITHUB_TOKEN = os.getenv("BOT")
FILE_PATH = "results/nodes.txt"

# 动态获取 7 天前的时间戳，格式为 YYYY-MM-DD
last_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

# 在关键词中加入 pushed:> 时间限制，确保搜索的是活跃仓库
SEARCH_QUERIES = [
    f'vmess:// pushed:>{last_week} extension:txt',
    f'vless:// pushed:>{last_week} extension:md',
    f'"proxies:" pushed:>{last_week} extension:yaml',
    f'clash node pushed:>{last_week} extension:yaml',
    f'ssr:// pushed:>{last_week} extension:txt'
]

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Mozilla/5.0"
}

def decode_base64_safe(data: str) -> str:
    data = re.sub(r'[^a-zA-Z0-9+/=]', '', data.strip())
    try:
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8', errors='ignore')
    except:
        return ""

def extract_nodes(text: str):
    if not text: return []
    found = set()
    # 匹配各类节点协议的正则
    pattern = r'(vmess|vless|ss|ssr|trojan|hysteria2?|tuic)://[a-zA-Z0-9%?&=._~#@:+/-]+'
    
    # 1. 直接匹配
    for match in re.finditer(pattern, text, re.I):
        found.add(match.group(0))

    # 2. 尝试 Base64 解码提取（处理订阅格式）
    decoded = decode_base64_safe(text)
    if decoded and '://' in decoded:
        for match in re.finditer(pattern, decoded, re.I):
            found.add(match.group(0))

    return list(found)

def fetch_and_process(item):
    try:
        # 略微停顿避免被反爬
        time.sleep(0.3)
        resp = requests.get(item['url'], headers=headers, timeout=10)
        if resp.status_code == 200:
            encoded_content = resp.json().get('content', '')
            raw_text = base64.b64decode(encoded_content).decode('utf-8', errors='ignore')
            return extract_nodes(raw_text)
    except:
        pass
    return []

def main():
    if not GITHUB_TOKEN:
        print("错误：未找到 BOT 变量")
        return

    all_items = []
    print(f"开始搜索最近更新的节点 (起始时间: {last_week})...")
    
    for query in SEARCH_QUERIES:
        # 代码搜索 API 限制每分钟 30 次，此处限制每组关键词搜索
        search_url = f"https://api.github.com/search/code?q={query}&per_page=50"
        res = requests.get(search_url, headers=headers)
        if res.status_code == 200:
            items = res.json().get('items', [])
            all_items.extend(items)
            print(f"关键词 [{query.split()[0]}] 找到 {len(items)} 个活跃文件")
        elif res.status_code == 403:
            print("触发 API 频率限制，暂停 20 秒...")
            time.sleep(20)
        time.sleep(2)

    if not all_items:
        print("未找到最近更新的候选文件。")
        return

    unique_nodes = set()
    # 稍微降低并发，提高稳定性
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(fetch_and_process, all_items)
        for node_list in results:
            if node_list:
                for node in node_list:
                    # 过滤过短的无效链接，排除常见的 GitHub 链接误伤
                    if len(node) > 25 and 'github.com' not in node.lower():
                        unique_nodes.add(node.strip())

    # 写入结果
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(list(unique_nodes))))

    print(f"--- 任务完成 ---")
    print(f"本次提取到最近更新的唯一节点数: {len(unique_nodes)}")

if __name__ == "__main__":
    main()
