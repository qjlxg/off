import os, re, base64, requests, time, csv, socket, yaml, threading, hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import urlencode

# ================= 配置区 =================
GITHUB_TOKEN = os.getenv("BOT")
FILE_PATH = "results/nodes.txt"
CSV_PATH = "results/stats.csv"
DAYS_BEFORE = 2 
# 协议质量权重：VLESS(Reality) > 其他协议
PROTOCOL_WEIGHTS = {"vless": 3, "hysteria2": 2, "hy2": 2, "tuic": 2}
# =========================================

headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "Mozilla/5.0"}
NODE_RE = re.compile(r'(vless|hysteria2?|hy2|tuic)://[a-zA-Z0-9%?&=._~#@:+/\[\]-]+', re.I)
visited_hashes = set() # 解析缓冲池：避免重复 decode 导致 CPU 浪费
processed_repos = set()

def fetch_with_retry(url):
    for i in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200: return resp
            if resp.status_code == 403: time.sleep(20)
        except: time.sleep(2)
    return None

def check_node_alive(node_url, timeout=2):
    try:
        match = re.search(r'://(?:.*@)?(?P<host>[^:/#?\[\]]+|\[[a-fA-F0-9:]+\]):(?P<port>\d+)', node_url)
        if not match: return False
        with socket.create_connection((match.group('host').strip('[]'), int(match.group('port'))), timeout=timeout):
            return True
    except: return False

def clash_to_link(p):
    try:
        p_type = p.get('type', '').lower()
        server, port = p.get('server'), p.get('port')
        if not server or not port: return None
        if p_type == 'vless':
            reality = p.get('reality-opts', {})
            params = {k: v for k, v in {"sni": p.get('sni'), "fp": p.get('client-fingerprint'), 
                      "pbk": reality.get('public-key'), "sid": reality.get('short-id')} if v}
            return f"vless://{p.get('uuid')}@{server}:{port}?{urlencode(params)}"
        elif p_type in ['hysteria2', 'hy2']:
            return f"hysteria2://{p.get('password', p.get('auth', ''))}@{server}:{port}?sni={p.get('sni', '')}"
        elif p_type == 'hysteria':
            return f"hysteria://{server}:{port}?auth={p.get('auth', '')}&sni={p.get('sni', '')}"
        elif p_type == 'tuic':
            return f"tuic://{p.get('uuid')}:{p.get('password')}@{server}:{port}?sni={p.get('sni', '')}"
    except: pass
    return None

def extract_nodes(text, depth=0):
    if depth > 2 or not text: return []
    text_hash = hashlib.md5(text.encode()).hexdigest()
    if text_hash in visited_hashes: return []
    visited_hashes.add(text_hash)
    
    found = set()
    for match in NODE_RE.finditer(text): found.add(match.group(0))
    if 'proxies:' in text:
        try:
            for p in yaml.safe_load(text).get('proxies', []):
                link = clash_to_link(p)
                if link: found.add(link)
        except: pass
    
    clean_text = re.sub(r'[^a-zA-Z0-9+/=]', '', text.strip())
    if len(clean_text) > 100:
        try:
            decoded = base64.b64decode(clean_text + '=' * (4 - len(clean_text) % 4)).decode('utf-8', 'ignore')
            if '://' in decoded or 'proxies:' in decoded:
                found.update(extract_nodes(decoded, depth + 1))
        except: pass
    return list(found)

def main():
    target_files, raw_repo_map = [], {}
    since = (datetime.now() - timedelta(days=DAYS_BEFORE)).strftime('%Y-%m-%d')
    keywords = ["clash", "v2ray", "sub", "proxy", "mihomo", "sing-box"]

    print(f"--- 步骤 1: 扫描活跃仓库 ---")
    for k in keywords:
        resp = fetch_with_retry(f"https://api.github.com/search/repositories?q={k} pushed:>{since}&sort=updated&per_page=10")
        if not resp: continue
        for r in resp.json().get('items', []):
            if r['full_name'] in processed_repos: continue
            processed_repos.add(r['full_name'])
            q = f"repo:{r['full_name']} (extension:txt OR extension:yaml OR extension:yml OR extension:md)"
            code_resp = fetch_with_retry(f"https://api.github.com/search/code?q={q}")
            if code_resp: target_files.extend(code_resp.json().get('items', []))
    
    print(f"--- 步骤 2: 解析与深度去重 ---")
    final_nodes, raw_repo_map = set(), {}
    for item in target_files:
        repo_name = item['repository']['full_name']
        resp = fetch_with_retry(item['url'])
        if not resp: continue
        try:
            nodes = extract_nodes(base64.b64decode(resp.json().get('content', '')).decode('utf-8', 'ignore'))
            for n in nodes:
                final_nodes.add(n)
                raw_repo_map.setdefault(repo_name, set()).add(n)
        except: pass

    print(f"--- 步骤 3: 存活探测与权重排序 ---")
    alive_nodes = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        for res in executor.map(lambda n: n if (n.split('://')[0].lower() in ['hysteria2', 'hy2', 'tuic'] or check_node_alive(n)) else None, final_nodes):
            if res: alive_nodes.append(res)
    
    # 按协议权重进行高质量排序
    alive_nodes.sort(key=lambda n: PROTOCOL_WEIGHTS.get(n.split('://')[0].lower(), 0), reverse=True)

    os.makedirs('results', exist_ok=True)
    with open(FILE_PATH, "w", encoding="utf-8") as f: f.write("\n".join(alive_nodes))
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["仓库", "有效去重节点数"])
        for r, n_set in sorted(raw_repo_map.items(), key=lambda x: len(x[1]), reverse=True):
            writer.writerow([r, len(n_set)])
    
    print(f"--- 任务完成，已输出: {len(alive_nodes)} 个高质量节点 ---")

if __name__ == "__main__":
    main()
