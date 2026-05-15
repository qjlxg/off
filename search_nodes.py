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

# 搜索组合
SEARCH_QUERIES = [
    'vmess:// extension:txt',
    'vless:// extension:md',
    '"proxies:" extension:yaml',
    'ssr:// extension:txt',
    'clash node extension:yaml'
]

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Mozilla/5.0"
}

# 终极正则：放宽了对字符的限制，确保能抓到完整的链接
NODE_RE = re.compile(
    r'(vmess|vless|ss|ssr|trojan|hysteria2?|tuic)://[a-zA-Z0-9%?&=._~#@:+/-]+',
    re.IGNORECASE
)

def decode_base64_safe(data: str) -> str:
    """深度解码 Base64，处理各种异常格式"""
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

    # 1. 直接正则匹配（处理明文和 YAML 内部的链接）
    raw_matches = NODE_RE.findall(text)
    # 注意：findall 如果有分组会只返回分组，这里我们需要完整的链接
    # 重新使用 finditer 获取完整匹配
    for match in re.finditer(r'(vmess|vless|ss|ssr|trojan|hysteria2?|tuic)://[a-zA-Z0-9%?&=._~#@:+/-]+', text, re.I):
        found.add(match.group(0))

    # 2. 尝试全文本 Base64 解码并再次匹配（处理订阅链接格式）
    decoded = decode_base64_safe(text)
    if decoded and '://' in decoded:
        for match in re.finditer(r'(vmess|vless|ss|ssr|trojan|hysteria2?|tuic)://[a-zA-Z0-9%?&=._~#@:+/-]+', decoded, re.I):
            found.add(match.group(0))

    # 3. 处理 URL 编码
    if '%3A%2F%2F' in text.upper():
        try:
            unquoted = unquote(text)
            for match in re.finditer(r'(vmess|vless|ss|ssr|trojan|hysteria2?|tuic)://[a-zA-Z0-9%?&=._~#@:+/-]+', unquoted, re.I):
                found.add(match.group(0))
        except: pass

    return list(found)

def fetch_and_process(item):
    try:
        # 增加随机延迟，防止被 GitHub API 屏蔽
        resp = requests.get(item['url'], headers=headers, timeout=10)
        if resp.status_code == 200:
            file_data = resp.json()
            # GitHub API 返回的 content 已经是 Base64 编码的
            encoded_content = file_data.get('content', '')
            # 第一次解码：从 GitHub API 的 Base64 转为明文文本
            raw_text = base64.b64decode(encoded_content).decode('utf-8', errors='ignore')
            # 第二次解析：从明文文本中提取节点
            return extract_nodes(raw_text)
    except:
        pass
    return []

def main():
    if not GITHUB_TOKEN:
        print("错误：未设置环境变量 BOT")
        return

    all_items = []
    print("开始多维度搜索...")
    for query in SEARCH_QUERIES:
        search_url = f"https://api.github.com/search/code?q={query}&per_page=100"
        res = requests.get(search_url, headers=headers)
        if res.status_code == 200:
            items = res.json().get('items', [])
            all_items.extend(items)
            print(f"搜索 [{query}]: 找到 {len(items)} 个文件")
        time.sleep(5) # 搜索接口限流严重，必须慢

    if not all_items:
        print("未搜索到任何文件")
        return

    unique_nodes = set()
    print(f"正在并行解析 {len(all_items)} 个文件...")

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_and_process, all_items)
        for node_list in results:
            if node_list:
                for node in node_list:
                    # 过滤掉一些明显的垃圾信息
                    if len(node) > 20 and 'github.com' not in node:
                        unique_nodes.add(node.strip())

    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(list(unique_nodes))))

    print(f"--- 任务结束 ---")
    print(f"总计提取唯一节点数量: {len(unique_nodes)}")
    print(f"结果已保存至: {FILE_PATH}")

if __name__ == "__main__":
    main()
