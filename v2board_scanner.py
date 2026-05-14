import asyncio
import aiohttp
import pandas as pd
from datetime import datetime
import ipaddress
import re

# ================= 优化配置 =================
TARGET_NETWORK = "125.78.0.0/16" 
# 增加 7001 (Xboard默认), 2053/2083/2096 (CF常用)
PORTS = [80, 443, 7001, 8443, 2053, 2083, 2096] 
CONCURRENT_LIMIT = 200 # 保持安全并发
TIMEOUT = 12

FINGERPRINTS = [
    r"/theme/v2board",
    r"/theme/Xboard",
    r"window\.v2board",
    r"window\.xboard",
    r"/assets/umi\.js",  # Xboard/Umi 框架核心
    r"/static/js/main\.js",
    r"v2board-config",
    r"__v2board__",
    r"v2-theme"
]

async def check_target(session, ip, port):
    # 自动识别协议：443及以上通常为 https
    protocol = "https" if port in [443, 8443, 2053, 2083, 2096] else "http"
    url = f"{protocol}://{ip}:{port}"
    
    try:
        # allow_redirects=True 非常重要，因为很多面板会跳转到 /login
        async with session.get(url, timeout=TIMEOUT, allow_redirects=True, ssl=False) as response:
            html = await response.text()
            
            # 只要 HTML 中命中任何一个特征
            hits = [fp for fp in FINGERPRINTS if re.search(fp, html, re.IGNORECASE)]
            
            if hits:
                print(f"🎯 [Hit] {url} | Found: {hits[0]}")
                return {
                    "url": url,
                    "ip": ip,
                    "port": port,
                    "tags": "|".join(hits),
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
    except:
        pass
    return None

async def main():
    network = ipaddress.ip_network(TARGET_NETWORK)
    hosts = list(network.hosts())
    
    connector = aiohttp.TCPConnector(limit=CONCURRENT_LIMIT, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for ip in hosts:
            for port in PORTS:
                tasks.append(check_target(session, str(ip), port))
        
        print(f"🔎 正在扫描网段: {TARGET_NETWORK} (共 {len(tasks)} 个点)...")
        results = await asyncio.gather(*tasks)
        
        found = [r for r in results if r]
        if found:
            pd.DataFrame(found).to_csv("v2board_results.csv", index=False, encoding='utf-8-sig')
            print(f"✅ 成功! 找到 {len(found)} 个目标。")
        else:
            print("❌ 本轮扫描未发现匹配目标。")

if __name__ == "__main__":
    asyncio.run(main())
