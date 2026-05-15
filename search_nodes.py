import os
import re
import base64
import requests
from concurrent.futures import ThreadPoolExecutor

# 配置
GITHUB_TOKEN = os.getenv("BOT")
# 搜索关键词，涵盖常见节点协议和配置文件名
SEARCH_KEYWORDS = 'vmess:// OR vless:// OR ss:// OR ssr:// OR trojan:// OR "proxies:" extension:yaml'
FILE_PATH = "results/nodes.txt"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# 匹配标准节点链接的正则
NODE_RE = re.compile(r'(vmess|vless|ss|ssr|trojan|hysteria2|tuic)://[^\s\'"<>]+')

def decode_base64(data):
    """尝试解码 Base64 字符串"""
    try:
        # 补全 padding
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8', errors='ignore')
    except:
        return ""

def extract_nodes(text):
    """从原始文本、YAML 或 Base64 中提取节点链接"""
    extracted = []
    
    # 1. 直接正则匹配明文链接
    extracted.extend(NODE_RE.findall(text))
    
    # 2. 检查是否是全文本 Base64 (常见于订阅链接内容)
    decoded = decode_base64(text.strip())
    if decoded:
        extracted.extend(NODE_RE.findall(decoded))
        
    # 3. 如果是 YAML 格式，正则依然能抓取到 proxies 列表下的链接部分
    # 这里也可以增加专门的 yaml 加载器，但正则对混杂文件的兼容性更好
    
    return extracted

def fetch_and_process(item):
    """并行任务：下载、解析并提取"""
    try:
        resp = requests.get(item['url'], headers=headers)
        if resp.status_code == 200:
            raw_content = base64.b64decode(resp.json().get('content', '')).decode('utf-8', errors='ignore')
            return extract_nodes(raw_content)
    except:
        pass
    return []

def main():
    if not GITHUB_TOKEN:
        print("错误：变量 BOT 为空")
        return

    print("正在从 GitHub 搜索潜在节点文件...")
    search_url = f"https://api.github.com/search/code?q={SEARCH_KEYWORDS}"
    search_resp = requests.get(search_url, headers=headers)
    
    if search_resp.status_code != 200:
        print(f"搜索失败: {search_resp.text}")
        return

    items = search_resp.json().get('items', [])
    unique_nodes = set()

    print(f"找到 {len(items)} 个候选文件，开始并行解析...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_and_process, items)
        for node_list in results:
            if node_list:
                # 统一清理节点末尾可能存在的换行或异常字符
                for node in node_list:
                    unique_nodes.add(node.strip())

    # 保存结果
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(list(unique_nodes))))
    
    print(f"处理完成：共提取到 {len(unique_nodes)} 个唯一节点。")

if __name__ == "__main__":
    main()
