import os
import base64
import requests
from concurrent.futures import ThreadPoolExecutor

# 从环境变量 BOT 中获取 Token
GITHUB_TOKEN = os.getenv("BOT")
# 搜索关键词：可以根据需要修改或扩充
SEARCH_KEYWORDS = 'proxies "vmess://" OR "vless://" OR "hysteria2://"'
FILE_PATH = "results/nodes.txt"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def search_github():
    print(f"开始搜索代理节点...")
    # 搜索包含节点协议特征的代码
    url = f"https://api.github.com/search/code?q={SEARCH_KEYWORDS}&sort=indexed"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get('items', [])
        else:
            print(f"搜索 API 请求失败: {response.status_code}")
            return []
    except Exception as e:
        print(f"请求异常: {e}")
        return []

def fetch_content(item):
    """并行获取文件源码"""
    try:
        resp = requests.get(item['url'], headers=headers)
        if resp.status_code == 200:
            content = resp.json().get('content', '')
            # GitHub API 返回的是 Base64 编码的内容
            return base64.b64decode(content).decode('utf-8', errors='ignore')
    except:
        pass
    return ""

def main():
    if not GITHUB_TOKEN:
        print("错误：未找到名为 BOT 的 Token 变量。")
        return

    items = search_github()
    if not items:
        print("未发现匹配结果。")
        return

    # 限制并行数量，避免触发 GitHub API 频率限制
    with ThreadPoolExecutor(max_workers=5) as executor:
        contents = list(executor.map(fetch_content, items))
    
    # 过滤空结果
    valid_data = [c.strip() for c in contents if c.strip()]
    
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write("\n\n".join(valid_data))
    
    print(f"任务完成，已保存 {len(valid_data)} 个文件的内容到 {FILE_PATH}")

if __name__ == "__main__":
    main()
