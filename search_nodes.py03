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
from urllib.parse import unquote, quote, urlparse, parse_qsl, urlencode

# ================= 配置区 =================
GITHUB_TOKEN = os.getenv("BOT")
FILE_PATH = "results/nodes.txt"
CSV_PATH = "results/stats.csv"
DAYS_BEFORE = 2 

# 各官方协议的标准可用核心参数白名单列表
PROTOCOL_WHITELISTS = {
    "vless": ["security", "sni", "type", "header_type", "host", "path", "flow", "encryption", "fp", "alpn", "pbk", "sid"],
    "hysteria": ["protocol", "auth", "peer", "insecure", "alpn", "up", "down", "mport", "obfs", "obfs-password"],
    "hysteria2": ["auth", "sni", "insecure", "obfs", "obfs-password"],
    "hy2": ["auth", "sni", "insecure", "obfs", "obfs-password"],
    "tuic": ["congestion_control", "udp_relay_mode", "alpn", "sni", "disable_sni"]
}
# =========================================

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Mozilla/5.0"
}

# 优化后的正则：仅捕获 vless, hysteria, hysteria2, hy2, tuic
NODE_RE = re.compile(r'(vless|hysteria2?|hy2|tuic)://[a-zA-Z0-9%?&=._~#@:+/\[\]-]+', re.I)

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
    
    # 强制安全检查：排除 vmess 和 trojan
    if base_url.lower().startswith(("vmess://", "trojan://")):
        return ""
    
    return f"{base_url}#{quote(repo_name)}"

def clash_to_link(proxy):
    """将 Clash 字典格式的代理转换为节点链接"""
    try:
        p_type = str(proxy.get('type', '')).lower()
        server = proxy.get('server')
        port = proxy.get('port')
        if not server or not port: return None

        # 精确筛选：仅保留 vless, hysteria, hysteria2, hy2, tuic
        if p_type == 'vless':
            uuid = proxy.get('uuid')
            params = f"sni={proxy.get('sni', '')}&type={proxy.get('network', 'tcp')}"
            return f"{p_type}://{uuid}@{server}:{port}?{params}"

        elif p_type in ['hysteria2', 'hy2']:
            auth = proxy.get('password', proxy.get('auth', ''))
            return f"hysteria2://{auth}@{server}:{port}?sni={proxy.get('sni', '')}"

        elif p_type == 'hysteria':
            auth = proxy.get('auth', '')
            return f"hysteria://{server}:{port}?auth={auth}&sni={proxy.get('sni', '')}"

        elif p_type == 'tuic':
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
                    # 确保重命名后返回的不是空字符串且属于指定协议
                    if renamed_node and renamed_node not in raw_collected_nodes:
                        raw_collected_nodes.add(renamed_node)
                        repo_node_count[repo_name] += 1

    print(f"\n--- 步骤 2.5: 节点参数级深度清洗与规范化去重 ---")
    seen_cores = set()
    unique_cores = []

    for node in raw_collected_nodes:
        # 1. 剥离原始备注
        core_part = node.split('#')[0].strip()
        if '://' not in core_part: 
            continue
            
        prefix, body = core_part.split('://', 1)
        prefix = prefix.lower()
        if prefix not in PROTOCOL_WHITELISTS: 
            continue

        # 2. 深度清洗与协议白名单强校验
        if '?' in body:
            main_body, query_string = body.split('?', 1)
            try:
                # 校验核心主体（格式应为 user@ip:port）
                main_body = main_body.strip().lstrip('/')
                if '@' not in main_body or ':' not in main_body.split('@')[-1]:
                    continue  # 结构不合法，直接排除
                
                # 获取该协议的白名单
                allowed_params = PROTOCOL_WHITELISTS[prefix]
                params = parse_qsl(query_string)
                
                # 过滤并保留白名单内的有效官方标准设置
                clean_params = []
                for k, v in params:
                    k_lower = k.lower().strip()
                    if k_lower in allowed_params:
                        clean_params.append((k_lower, v.strip()))
                
                # 稳定排序并拼接
                clean_params.sort()
                if clean_params:
                    clean_query = urlencode(clean_params)
                    standard_core = f"{prefix}://{main_body}?{clean_query}"
                else:
                    standard_core = f"{prefix}://{main_body}"
            except:
                continue  # 解析异常的数据直接抛弃
        else:
            main_body = body.strip().lstrip('/')
            if '@' not in main_body or ':' not in main_body.split('@')[-1]:
                continue
            standard_core = f"{prefix}://{main_body}"
            
        if standard_core not in seen_cores:
            seen_cores.add(standard_core)
            unique_cores.append(standard_core)

    # 稳定排序
    unique_cores.sort()

    # 重新附加纯数字自增序号生成测试基准列表
    deduplicated_nodes_list = [f"{core}#{idx}" for idx, core in enumerate(unique_cores, start=1)]

    print(f"\n--- 步骤 3: 节点过滤与测速 (Hy2/Tuic 直接保留) ---")
    final_nodes = []
    
    def test_node(node_url):
        lower_url = node_url.lower()
        # 增加对标准 hysteria:// 的放行支持
        if lower_url.startswith(("hysteria2://", "hy2://", "hysteria://", "tuic://")):
            return node_url
        if check_node_alive(node_url):
            return node_url
        return None

    with ThreadPoolExecutor(max_workers=20) as executor:
        check_results = executor.map(test_node, deduplicated_nodes_list)
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
    print(f"原始收集节点: {len(raw_collected_nodes)}")
    print(f"深度去重后唯一核心数: {len(unique_cores)}")
    print(f"最终保留节点: {len(final_nodes)} (含跳过测试的 UDP 节点)")

if __name__ == "__main__":
    main()
