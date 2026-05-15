import os
import re
import base64
import requests
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

# 配置
GITHUB_TOKEN = os.getenv("BOT")
FILE_PATH = "results/nodes.txt"

# 优化搜索策略：拆分为多个关键词组合，增加命中率
# GitHub API 限制 q 参数不能太长，这里选取最有效的组合
SEARCH_QUERIES = [
    'vmess:// extension:txt',
    'vless:// extension:md',
    '"proxies:" extension:yaml',
    'sub_link extension:txt',
    'clash node extension:yaml'
]

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Mozilla/5.0"
}

# 增强正则：支持更多现代协议
NODE_RE = re.compile(
    r'(?i)(vmess|vless|ss|ssr|trojan|hysteria2?|tuic|shadowsocks)://'
    r'[a-zA-Z0-9%?&=._~#@:/-]+'
)

def decode_base64(data: str) -> str:
    data = data.strip()
    try:
        # 移除可能存在的空白符并补全 padding
        data = re.sub(r'\s+', '', data)
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8', errors='ignore')
    except:
        return ""

def extract_nodes(text: str):
    if not text: return []
    extracted = set()
    # 1. 明文提取
    extracted.update(NODE_RE.findall(text))
    # 2. Base64 提取
    decoded = decode_base64(text)
    if decoded:
        extracted.update(NODE_RE.findall(decoded))
    # 3. URL 解码提取
    if '%3' in text:
        try:
            extracted.update(NODE_RE.findall(unquote(text)))
        except: pass
    return list(extracted)

def fetch_and_process(item):
    try:
        # 避免请求过快
        time.sleep(0.5) 
        resp = requests.get(item['url'], headers=headers, timeout=10)
        if resp.status_code == 200:
            content = resp.json().get('content', '')
            raw_content = base64.b64decode(content).decode('utf-8', errors='ignore')
            return extract_nodes(raw_content)
    except:
        pass
    return []

def main():
    if not GITHUB_TOKEN:
        print("错误：未检测到环境变量 BOT (Token)")
        return

    all_items = []
    print("开始多维度搜索...")
    
    for query in SEARCH_QUERIES:
        # 每种关键词搜前 2 页（每页 50 个）
        for page in range(1, 3):
            search_url = f"https://api.github.com/search/code?q={query}&per_page=50&page={page}"
            res = requests.get(search_url, headers=headers)
            if res.status_code == 200:
                items = res.json().get('items', [])
                all_items.extend(items)
                print(f"搜索 [{query}] 第 {page} 页: 找到 {len(items)} 个文件")
            elif res.status_code == 403:
                print("触发 API 频率限制，稍等...")
                time.sleep(30)
            
            # GitHub Search API 频率限制很严，每页之间稍微停顿
            time.sleep(2)

    if not all_items:
        print("搜索结果为空，请检查 Token 权限或尝试更换关键词。")
        return

    print(f"去重后共计 {len(all_items)} 个候选文件，开始并行解析内容...")
    unique_nodes = set()

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_and_process, all_items)
        for node_list in results:
            if node_list:
                for node in node_list:
                    if len(node) > 15: # 过滤极短的无效链接
                        unique_nodes.add(node.strip())

    # 写入结果
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    # 读取旧数据合并去重（可选）
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(list(unique_nodes))))

    print(f"成功！保存了 {len(unique_nodes)} 个节点到 {FILE_PATH}")

if __name__ == "__main__":
    main()
