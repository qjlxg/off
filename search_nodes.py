import os
import re
import base64
import requests
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

# 配置
GITHUB_TOKEN = os.getenv("BOT")
FILE_PATH = "results/nodes.txt"

# 更强的搜索关键词
SEARCH_KEYWORDS = (
    'vmess:// OR vless:// OR ss:// OR ssr:// OR trojan:// OR hysteria2:// OR tuic:// OR '
    '"proxies:" OR "proxy-groups:" extension:yaml OR extension:yml OR extension:txt OR '
    'clash OR v2ray OR xray'
)

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Mozilla/5.0"
}

# 改进后的正则 - 非捕获组 + 支持更多协议 + 更好的字符范围
NODE_RE = re.compile(
    r'(?i)(vmess|vless|ss|ssr|trojan|hysteria2?|tuic|shadowsocks)://'
    r'[^\\s\'"<>{}|\\]+'
)

def decode_base64(data: str) -> str:
    """尝试解码 Base64（支持订阅内容）"""
    data = data.strip()
    try:
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8', errors='ignore')
    except:
        return ""


def extract_nodes(text: str):
    """提取节点链接"""
    if not text:
        return []
    
    extracted = set()

    # 1. 直接匹配明文节点
    extracted.update(NODE_RE.findall(text))

    # 2. 尝试整体 Base64 解码（常见于订阅）
    decoded = decode_base64(text)
    if decoded:
        extracted.update(NODE_RE.findall(decoded))

    # 3. 处理 URL 编码的情况（如 %3A%2F%2F）
    if '%3A%2F%2F' in text:
        try:
            decoded_url = unquote(text)
            extracted.update(NODE_RE.findall(decoded_url))
        except:
            pass

    return list(extracted)


def fetch_and_process(item):
    """下载并解析单个文件"""
    try:
        resp = requests.get(item['url'], headers=headers, timeout=15)
        if resp.status_code != 200:
            return []

        content = resp.json().get('content', '')
        if not content:
            return []

        raw_content = base64.b64decode(content).decode('utf-8', errors='ignore')
        return extract_nodes(raw_content)
    except Exception as e:
        # print(f"Error processing {item.get('html_url')}: {e}")  # 调试时开启
        return []


def main():
    if not GITHUB_TOKEN:
        print("错误：环境变量 BOT (GITHUB_TOKEN) 为空")
        return

    print("正在搜索 GitHub...")
    search_url = f"https://api.github.com/search/code?q={SEARCH_KEYWORDS}&per_page=100"
    
    search_resp = requests.get(search_url, headers=headers)
    
    if search_resp.status_code != 200:
        print(f"搜索失败: {search_resp.status_code} - {search_resp.text[:500]}")
        return

    items = search_resp.json().get('items', [])
    print(f"找到 {len(items)} 个候选文件，开始提取...")

    unique_nodes = set()

    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(fetch_and_process, items)
        for node_list in results:
            for node in node_list:
                if node and len(node) > 10:   # 简单过滤无效短链接
                    unique_nodes.add(node.strip())

    # 保存
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(unique_nodes)))

    print(f"完成！共提取到 {len(unique_nodes)} 个唯一节点，已保存至 {FILE_PATH}")


if __name__ == "__main__":
    main()