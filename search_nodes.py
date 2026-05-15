import os
import re
import base64
import requests
import time
import csv
import socket
import json
import yaml  
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, quote, urlparse

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

# 优化后的正则：支持更多特殊字符，确保 hysteria2/tuic 的参数完整提取
NODE_RE = re.compile(r'(vmess|vless|ss|ssr|trojan|hysteria2?|tuic)://[a-zA-Z0-9%?&=._~#@:+/\[\]-]+', re.I)

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

def check_node_alive(node_url, timeout=3):
    """通过 TCP 握手检测节点连通性 - 已缩短超时时间为 3s"""
    try:
        # 匹配格式: @host:port? 或 ://host:port?
        match = re.search(r'://(?:.*@)?(?P<host>[^:/#?\[\]]+|\[[a-fA-F0-9:]+\]):(?P<port>\d+)', node_url)
        if not match:
            return False
        
        host = match.group('host').strip('[]')
        port = int(match.group('port'))
        
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def clean_and_rename_node(node_url, repo_name):
    """删除原备注并以仓库名命名，保留所有参数"""
    base_url = node_url.split('#')[0]
    
    if base_url.lower().startswith("vmess://"):
        try:
            v_data = base_url[8:]
            missing_padding = len(v_data) % 4
            if missing_padding: v_data += '=' * (4 - missing_padding)
            v_json = json.loads(base64.b64decode(v_data).decode('utf-8'))
            v_json['ps'] = repo_name 
            new_v_data = base64.b64encode(json.dumps(v_json).encode('utf-8')).decode('utf-8')
            return f"vmess://{new_v_data}"
        except:
            return f"{base_url}#{quote(repo_name)}"
    
    return f"{base_url}#{quote(repo_name)}"

def clash_to_link(proxy):
    """将 Clash 字典格式的代理转换为节点链接"""
    try:
        p_type = str(proxy.get('type', '')).lower()
        server = proxy.get('server')
        port = proxy.get('port')
        if not server or not port: return None

        if p_type == 'ss':
            cipher = proxy.get('cipher')
            password = proxy.get('password')
            auth = base64.b64encode(f"{cipher}:{password}".encode()).decode()
            return f"ss://{auth}@{server}:{port}"
        
        elif p_type == 'vmess':
            v_json = {
                "v": "2", "ps": "", "add": str(server), "port": str(port),
                "id": str(proxy.get('uuid')), "aid": str(proxy.get('alterId', 0)),
                "scy": proxy.get('cipher', 'auto'), "net": proxy.get('network', 'tcp'),
                "type": "none", "host": "", "path": "", "tls": "tls" if proxy.get('tls') else ""
            }
            if v_json['net'] in ['ws', 'grpc']:
                opts = proxy.get('ws-opts', {}) if v_json['net'] == 'ws' else proxy.get('grpc-opts', {})
                v_json['host'] = opts.get('headers', {}).get('Host', '')
                v_json['path'] = opts.get('path', '') if v_json['net'] == 'ws' else opts.get('grpc-service-name', '')
            v_data = base64.b64encode(json.dumps(v_json).encode()).decode()
            return f"vmess://{v_data}"

        elif p_type in ['vless', 'trojan']:
            uuid = proxy.get('uuid') or proxy.get('password')
            params = f"sni={proxy.get('sni', '')}&type={proxy.get('network', 'tcp')}"
            return f"{p_type}://{uuid}@{server}:{port}?{params}"

        elif p_type in ['hysteria2', 'hy2']:
            auth = proxy.get('password', proxy.get('auth', ''))
            return f"hysteria2://{auth}@{server}:{port}?sni={proxy.get('sni', '')}"

        elif p_type == 'schema_tuic' or p_type == 'tuic':
            uuid = proxy.get('uuid')
            passw = proxy.get('password')
            return f"tuic://{uuid}:{passw}@{server}:{port}?sni={proxy.get('sni', '')}"
            
    except:
        pass
    return None

def extract_nodes(text):
    if not text: return []
    found = set()
    
    # 1. 直接正则匹配链接
    for match in NODE_RE.finditer(text):
        found.add(match.group(0))
        
    # 2. 尝试解析 YAML (Clash)
    if 'proxies:' in text:
        try:
            config = yaml.safe_load(text)
            if isinstance(config, dict) and 'proxies' in config:
                for p in config['proxies']:
                    link = clash_to_link(p)
                    if link: found.add(link)
        except:
            pass

    # 3. 尝试 Base64 解码提取
    try:
        clean_text = re.sub(r'[^a-zA-Z0-9+/=]', '', text.strip())
        missing_padding = len(clean_text) % 4
        if missing_padding: clean_text += '=' * (4 - missing_padding)
        decoded = base64.b64decode(clean_text).decode('utf-8', errors='ignore')
        if '://' in decoded or 'proxies:' in decoded:
            found.update(extract_nodes(decoded)) # 递归处理解码内容
    except:
        pass
    return list(found)

def process_file_item(item):
    repo_name = item['repository']['full_name']
    
    # 排除来自特定仓库的节点
    exclude_repos = ["sinavm", "qjlxg"]
    if any(ex in repo_name.lower() for ex in exclude_repos):
        return repo_name, []

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
    raw_collected_nodes = set()

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(process_file_item, target_files)
        for repo_name, nodes in results:
            if repo_name not in repo_node_count:
                repo_node_count[repo_name] = 0
            
            for n in nodes:
                n = n.strip()
                if len(n) > 20 and 'github.com' not in n.lower():
                    renamed_node = clean_and_rename_node(n, repo_name)
                    if renamed_node not in raw_collected_nodes:
                        raw_collected_nodes.add(renamed_node)
                        repo_node_count[repo_name] += 1

    print(f"\n--- 步骤 3: 节点过滤与测速 (Hy2/Tuic 直接保留) ---")
    final_nodes = []
    
    def test_node(node_url):
        lower_url = node_url.lower()
        if lower_url.startswith(("hysteria2://", "hy2://", "tuic://")):
            return node_url
        if check_node_alive(node_url):
            return node_url
        return None

    with ThreadPoolExecutor(max_workers=20) as executor:
        check_results = executor.map(test_node, list(raw_collected_nodes))
        for res in check_results:
            if res:
                final_nodes.append(res)

    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["仓库名称", "发现节点数量"])
        sorted_stats = sorted(repo_node_count.items(), key=lambda x: x[1], reverse=True)
        for row in sorted_stats:
            writer.writerow(row)

    with open(FILE_PATH, "w", encoding="utf-8") as f:
        if final_nodes:
            f.write("\n".join(sorted(final_nodes)))
        else:
            f.write("")

    print(f"\n--- 任务完成 ---")
    print(f"共发现唯一节点: {len(raw_collected_nodes)}")
    print(f"最终保留节点: {len(final_nodes)} (含跳过测试的 UDP 节点)")

if __name__ == "__main__":
    main()
