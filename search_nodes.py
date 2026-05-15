import os
import base64
import requests
from concurrent.futures import ThreadPoolExecutor

# 配置
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SEARCH_QUERY = os.getenv("BOT")
REPO_DEST = os.getenv("GITHUB_REPOSITORY")
FILE_PATH = "results/nodes.txt"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def search_github():
    print(f"正在使用关键词 '{SEARCH_QUERY}' 搜索节点...")
    # 搜索包含该关键词的代码
    url = f"https://api.github.com/search/code?q={SEARCH_QUERY}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"搜索失败: {response.text}")
        return []
    
    items = response.json().get('items', [])
    return items

def fetch_content(item):
    """并行调用的函数：获取具体文件内容"""
    try:
        content_url = item['url']
        resp = requests.get(content_url, headers=headers)
        if resp.status_code == 200:
            encoded_content = resp.json().get('content', '')
            # 解码并简单过滤（此处可根据需求增加具体的节点提取正则）
            return base64.b64decode(encoded_content).decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"获取内容出错: {e}")
    return ""

def main():
    if not SEARCH_QUERY:
        print("未设置 BOT 变量，退出。")
        return

    items = search_github()
    results = []

    # 并行运行获取任务
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_results = list(executor.map(fetch_content, items))
    
    # 汇总结果
    valid_results = [r for r in future_results if r]
    
    # 确保目录存在并保存
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(valid_results))
    
    print(f"已保存 {len(valid_results)} 个搜索结果。")

if __name__ == "__main__":
    main()
