import os
import re
import base64
import requests
import time
import csv
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, quote

# ================= 配置区 =================
GITHUB_TOKEN = os.getenv("BOT")
FILE_PATH = "results/nodes.txt"
CSV_PATH = "results/stats.csv"
DAYS_BEFORE = 2 
# =========================================

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Mozilla/5.0"
}

# 匹配节点基础协议和链接
NODE_RE = re.compile(r'(vmess|vless|ss|ssr|trojan|hysteria2?|tuic)://[a-zA-Z0-9%?&=._~#@:+/-]+', re.I)

def fetch_with_retry(url, max_retries=3):
    for i in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 403:
                wait_time = (i + 1) * 20
                print(f"  [!] 触发限流，等待 {wait_time}s...")
                time.sleep(wait_time)
        except Exception:
            time.sleep(2)
    return None

def clean_and_rename_node(node_url, repo_name):
    """删除原备注并以仓库名命名"""
    # 1. 移除原有 # 及其后面的备注内容
    base_url = node_url.split('#')[0]
    
    # 2. 特殊处理 vmess (vmess 的备注有时加密在 json 里的 ps 字段)
    if base_url.lower().startswith("vmess://"):
        try:
            v_data = base_url[8:]
            # 自动补全 padding
            missing_padding = len(v_data) % 4
            if missing_padding: v_data += '=' * (4 - missing_padding)
            import json
            v_json = json.loads(base64.b64decode(v_data).decode('utf-8'))
            v_json['ps'] = repo_name  # 修改备注字段
            new_v_data = base64.b64encode(json.dumps(v_json).encode('utf-8')).decode('utf-8')
            return f"vmess://{new_v_data}"
        except:
            return f"{base_url}#{quote(repo_name)}"
    
    # 3. 其他协议 (vless, ss, trojan 等) 直接在末尾加 #仓库名
    return f"{base_url}#{quote(repo_name)}"

def extract_nodes(text):
    if not text: return []
    found = set()
    # 直接正则匹配
    for match in NODE_RE.finditer(text):
        found.add(match.group(0))
    # 尝试 Base64 解码提取
    try:
        clean_text = re.sub(r'[^a-zA-Z0-9+/=]', '', text.strip())
        missing_padding = len(clean_text) % 4
        if missing_padding: clean_text += '=' * (4 - missing_padding)
        decoded = base64.b64decode(clean_text).decode('utf-8', errors='ignore')
        if '://' in decoded:
            for match in NODE_RE.finditer(decoded):
                found.add(match.group(0))
    except:
        pass
    return list(found)

def process_file_item(item):
    repo_name = item['repository']['full_name']
    resp = fetch_with_retry(item['url'])
    if resp:
        try:
            data = resp.json()
            raw_text = base64.b64decode(data.get('content', '')).decode('utf-8', errors='ignore')
            nodes = extract_nodes(raw_text)
            return repo_name, nodes
        except:
            pass
    return repo_name, []

def main():
    if not GITHUB_TOKEN:
        print("错误：请配置环境变量 BOT")
        return

    target_files = []
    since_date = (datetime.now() - timedelta(days=DAYS_BEFORE)).strftime('%Y-%m-%d')
    
    queries = [
        f'clash config pushed:>{since_date}',
        f'v2ray nodes pushed:>{since_date}',
        f'sub link pushed:>{since_date}'
    ]

    print(f"--- 步骤 1: 扫描最近 {DAYS_BEFORE} 天活跃仓库 ---")
    repo_stats_initial = {}

    for q in queries:
        repo_resp = fetch_with_retry(f"https://api.github.com/search/repositories?q={q}&sort=updated&per_page=15")
        if repo_resp:
            repos = repo_resp.json().get('items', [])
            for r in repos:
                repo_name = r['full_name']
                if repo_name in repo_stats_initial: continue
                
                code_url = f"https://api.github.com/search/code?q=repo:{repo_name}+extension:txt+extension:yaml+extension:md"
                code_resp = fetch_with_retry(code_url)
                if code_resp:
                    items = code_resp.json().get('items', [])
                    target_files.extend(items)
                    repo_stats_initial[repo_name] = len(items)
                    print(f"  + 发现仓库: {repo_name} ({len(items)} 个文件)")
                time.sleep(2)

    print(f"\n--- 步骤 2: 解析并重命名节点 ---")
    repo_node_count = {}
    processed_nodes = set() # 用于 nodes.txt 的去重

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(process_file_item, target_files)
        for repo_name, nodes in results:
            if repo_name not in repo_node_count:
                repo_node_count[repo_name] = 0
            
            for n in nodes:
                n = n.strip()
                if len(n) > 20 and 'github.com' not in n.lower():
                    # 处理节点：删除旧备注，添加新备注
                    renamed_node = clean_and_rename_node(n, repo_name)
                    if renamed_node not in processed_nodes:
                        processed_nodes.add(renamed_node)
                        repo_node_count[repo_name] += 1

    # 保存统计 CSV
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["仓库名称", "有效节点数量"])
        sorted_stats = sorted(repo_node_count.items(), key=lambda x: x[1], reverse=True)
        for row in sorted_stats:
            writer.writerow(row)

    # 保存 nodes.txt (已经是 节点#仓库名 格式)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(list(processed_nodes))))

    print(f"\n--- 任务完成 ---")
    print(f"唯一节点数: {len(processed_nodes)}，已重命名。")

if __name__ == "__main__":
    main()
