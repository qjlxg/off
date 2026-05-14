import asyncio
import aiohttp
import pandas as pd
from datetime import datetime
import ipaddress
import re

# 配置
TARGET_NETWORK = "125.78.0.0/16"
PORTS = [80, 443, 8080, 8443] 
CONCURRENT_LIMIT = 1000 # 提高并发
TIMEOUT = 4

# 识别指纹库
FINGERPRINTS = [
    r"/theme/v2board",
    r"/theme/Xboard",
    r"/assets/umi\.js",
    r"window\.v2board",
    r"window\.xboard",
    r"/static/js/main\.js",
    r"v2board-config"
]

async def check_target(session, ip, port):
    protocol = "https" if port in [443, 8443] else "http"
    url = f"{protocol}://{ip}:{port}"
    try:
        async with session.get(url, timeout=TIMEOUT, allow_redirects=True, ssl=False) as response:
            if response.status != 200:
                return None
                
            html = await response.text()
            
            # 匹配任何一个指纹
            matched = [fp for fp in FINGERPRINTS if re.search(fp, html, re.IGNORECASE)]
            
            if matched:
                print(f"[+] Found Match: {url} | Hits: {matched}")
                return {
                    "url": url,
                    "ip": ip,
                    "port": port,
                    "fingerprints": "|".join(matched),
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
    except:
        pass
    return None

async def main():
    network = ipaddress.ip_network(TARGET_NETWORK)
    connector = aiohttp.TCPConnector(limit=CONCURRENT_LIMIT, ssl=False)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for ip in network.hosts():
            for port in PORTS:
                tasks.append(check_target(session, str(ip), port))
        
        print(f"🚀 开始探测 {TARGET_NETWORK}，共计 {len(tasks)} 个请求...")
        results = await asyncio.gather(*tasks)
        
        found_sites = [r for r in results if r]
        
        if found_sites:
            df = pd.DataFrame(found_sites)
            df.to_csv("v2board_results.csv", index=False, encoding='utf-8-sig')
            print(f"✅ 扫描完成！找到 {len(found_sites)} 个目标。")
        else:
            print("⚠️ 扫描完成，未发现匹配站点。")

if __name__ == "__main__":
    asyncio.run(main())
