import asyncio
import aiohttp
import pandas as pd
from datetime import datetime
import ipaddress
import re

# ================= 适配版配置 =================
# 建议先测试你样本所在的网段，例如 104.168.0.0/16
TARGET_NETWORK = "192.3.0.0/16" 
# 包含你提供的 7001 以及 Xboard 常见的 Web 端口
PORTS = [80, 443, 7001, 8443, 2053, 2083, 2096] 
CONCURRENT_LIMIT = 200 
TIMEOUT = 12

# 增强指纹库
FINGERPRINTS = [
    r"/theme/v2board",
    r"/theme/Xboard",
    r"/assets/umi\.js",      # 核心框架特征
    r"window\.v2board",
    r"window\.xboard",
    r"v2board-config",
    r"/static/js/main\.js",
    r"auth-v2board"          # 登录页常见标识
]

async def check_target(session, ip, port):
    # 逻辑：7001 通常是 http，443/8443 等通常是 https
    if port in [443, 8443, 2053, 2083, 2096]:
        protocols = ["https"]
    elif port == 7001:
        protocols = ["http"]
    else:
        protocols = ["http", "https"]

    for proto in protocols:
        url = f"{proto}://{ip}:{port}"
        try:
            async with session.get(url, timeout=TIMEOUT, allow_redirects=True, ssl=False) as response:
                if response.status != 200:
                    continue
                
                text = await response.text()
                hits = [fp for fp in FINGERPRINTS if re.search(fp, text, re.IGNORECASE)]
                
                if hits:
                    print(f"🎯 命中目标: {url} | 指纹: {hits[0]}")
                    return {
                        "url": url,
                        "ip": ip,
                        "port": port,
                        "fingerprint": hits[0],
                        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
        except:
            pass
    return None

async def main():
    network = ipaddress.ip_network(TARGET_NETWORK)
    hosts = list(network.hosts())
    
    # 使用限制并发的连接池
    connector = aiohttp.TCPConnector(limit=CONCURRENT_LIMIT, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for ip in hosts:
            for port in PORTS:
                tasks.append(check_target(session, str(ip), port))
        
        print(f"🔍 正在探测网段: {TARGET_NETWORK}...")
        print(f"📊 预计发送 {len(tasks)} 个探测请求")

        results = await asyncio.gather(*tasks)
        found = [r for r in results if r]
        
        if found:
            df = pd.DataFrame(found)
            df.to_csv("v2board_results.csv", index=False, encoding='utf-8-sig')
            print(f"✅ 扫描完成，导出 {len(found)} 条结果。")
        else:
            print("❌ 本轮扫描未发现目标。")

if __name__ == "__main__":
    asyncio.run(main())
