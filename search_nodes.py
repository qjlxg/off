import os
import re
import base64
import requests
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

# ================= 配置区 =================
GITHUB_TOKEN = os.getenv("BOT")
FILE_PATH = "results/nodes.txt"
# 搜索最近 3 天更新过的仓库，可以根据需求改为 1 或 7
DAYS_BEFORE = 3 
# =========================================

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Mozilla/5.0"
}

NODE_RE = re.compile(r'(vmess|vless|ss|ssr|trojan|hysteria2?|tuic)://[a-zA-Z0-9%?&=._~#@:+/-]+', re.I)

def fetch_with_retry(url, max_retries=3):
    """带重试机制的请求函数"""
    for i in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 403: # 触发速率限制
                wait_time = (i + 1) * 10
                print(f"  [!] 触发限流，等待 {wait_time}s...")
                time.sleep(wait_time)
        except Exception:
            time.sleep(2)
    return None

def extract_nodes(text):
    """多重解析提取节点"""
    if not text: return []
    found = set()
    
    # 1. 尝试直接正则匹配
    for match in NODE_RE.finditer(text):
        found.add(match.group(0))
        
    # 2. 尝试 Base64 解码提取 (处理订阅链接格式)
    try:
        # 清洗 base64 常见干扰字符
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
    """解析单个文件 API 返回的内容"""
    resp = fetch_with_retry(item['url'])
    if resp:
        try:
            data = resp.json()
            raw_text = base64.b64decode(data.get('content', '')).decode('utf-8', errors='ignore')
            return extract_nodes(raw_text)
        except:
            pass
    return []

def main():
    if not GITHUB_TOKEN:
        print("错误：请配置环境变量 BOT")
        return

    target_files = []
    since_date = (datetime.now() - timedelta(days=DAYS_BEFORE)).strftime('%Y-%m-%d')
    
    # 搜索关键词组合
    queries = [
        f'clash config pushed:>{since_date}',
        f'v2ray nodes pushed:>{since_date}',
        f'sub link pushed:>{since_date}'
    ]

    print(f"--- 步骤 1: 扫描最近 {DAYS_BEFORE} 天活跃仓库 ---")
    for q in queries:
        repo_resp = fetch_with_retry(f"https://api.github.com/search/repositories?q={q}&sort=updated&per_page=15")
        if repo_resp:
            repos = repo_resp.json().get('items', [])
            for r in repos:
                repo_name = r['full_name']
                # 在该仓库搜索潜力文件
                code_url = f"https://api.github.com/search/code?q=repo:{repo_name}+extension:txt+extension:yaml+extension:md"
                code_resp = fetch_with_retry(code_url)
                if code_resp:
                    items = code_resp.json().get('items', [])
                    target_files.extend(items)
                    print(f"  + 发现仓库: {repo_name} ({len(items)} 个候选文件)")
                time.sleep(2) # 严格遵守 Search API 限流

    if not target_files:
        print("未发现活跃文件。")
        return

    print(f"\n--- 步骤 2: 并行解析 {len(target_files)} 个文件 ---")
    final_nodes = set()
    
    with ThreadPoolExecutor(max_workers=5) as executor: # 降低并发，确保持续稳定
        results = executor.map(process_file_item, target_files)
        for nodes in results:
            for n in nodes:
                # 简单过滤掉太短或包含 github 域名的非节点链接
                if len(n) > 20 and 'github.com' not in n.lower():
                    final_nodes.add(n.strip())

    # 保存
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        # 排序保存，方便查看变化
        f.write("\n".join(sorted(list(final_nodes))))

    print(f"\n--- 任务成功结束 ---")
    print(f"总计获取唯一节点: {len(final_nodes)}")
    print(f"结果文件: {FILE_PATH}")

if __name__ == "__main__":
    main()
