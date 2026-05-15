import os
import re
import base64
import requests
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# 配置
GITHUB_TOKEN = os.getenv("BOT")
FILE_PATH = "results/nodes.txt"

# 1. 策略：搜索最近 3 天内活跃的仓库（代码搜索不支持 pushed，但仓库搜索支持）
last_3_days = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
REPO_QUERIES = [
    f'clash config pushed:>{last_3_days}',
    f'v2ray nodes pushed:>{last_3_days}',
    f'sub link pushed:>{last_3_days}'
]

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Mozilla/5.0"
}

# 节点匹配正则
NODE_RE = re.compile(r'(vmess|vless|ss|ssr|trojan|hysteria2?|tuic)://[a-zA-Z0-9%?&=._~#@:+/-]+', re.I)

def fetch_content_from_url(url):
    """直接通过 URL 获取内容并解析"""
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            # 如果是 API 返回的 JSON (来自 search/code)
            if 'content' in resp.json():
                text = base64.b64decode(resp.json()['content']).decode('utf-8', errors='ignore')
            else:
                text = resp.text
            
            return list(set(m.group(0) for m in NODE_RE.finditer(text)))
    except:
        pass
    return []

def main():
    if not GITHUB_TOKEN:
        print("错误：未找到 BOT 变量")
        return

    target_files = []
    print(f"步骤 1: 寻找最近 3 天活跃的候选仓库...")

    for q in REPO_QUERIES:
        # 搜索仓库
        repo_url = f"https://api.github.com/search/repositories?q={q}&sort=updated&per_page=10"
        res = requests.get(repo_url, headers=headers)
        if res.status_code == 200:
            repos = res.json().get('items', [])
            for r in repos:
                full_name = r['full_name']
                # 在该仓库内搜索相关后缀文件
                code_url = f"https://api.github.com/search/code?q=repo:{full_name}+extension:txt+extension:yaml+extension:md"
                c_res = requests.get(code_url, headers=headers)
                if c_res.status_code == 200:
                    items = c_res.json().get('items', [])
                    target_files.extend(items)
                    print(f"  来自 {full_name} 的候选文件: {len(items)} 个")
                time.sleep(2) # 避开 code search 的严苛限流
        time.sleep(2)

    if not target_files:
        # 如果仓库搜索太严，退回到普通的关键词代码搜索（去掉 pushed 参数）
        print("活跃仓库未匹配到文件，尝试直接代码搜索...")
        fallback_queries = ['vmess:// extension:txt', '"proxies:" extension:yaml']
        for fq in fallback_queries:
            res = requests.get(f"https://api.github.com/search/code?q={fq}&per_page=50", headers=headers)
            if res.status_code == 200:
                target_files.extend(res.json().get('items', []))

    print(f"步骤 2: 开始解析 {len(target_files)} 个文件内容...")
    unique_nodes = set()

    with ThreadPoolExecutor(max_workers=10) as executor:
        # 这里提取的是 item['url']，即文件内容的 API 地址
        results = executor.map(fetch_content_from_url, [f['url'] for f in target_files])
        for node_list in results:
            if node_list:
                for node in node_list:
                    if len(node) > 20 and 'github.com' not in node.lower():
                        unique_nodes.add(node.strip())

    # 保存
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(list(unique_nodes))))

    print(f"--- 任务完成 ---")
    print(f"提取到唯一节点数: {len(unique_nodes)}")

if __name__ == "__main__":
    main()
