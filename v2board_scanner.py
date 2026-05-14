import asyncio
import aiohttp
import pandas as pd
from datetime import datetime
import ipaddress
import re
import random

# ================= 配置区 =================
TARGET_NETWORK = "125.78.0.0/16"
# 仅扫描最可能的端口，减少无效探测
PORTS = [80, 443, 8443] 
# 安全并发值：建议 100-300，既能跑完 /16 且不易被 GitHub 标记
CONCURRENT_LIMIT = 200   
TIMEOUT = 10  # 增加超时以应对远距离探测

# 指纹特征库
FINGERPRINTS = [
    r"/theme/v2board",
    r"/theme/Xboard",
    r"/assets/umi\.js",
    r"window\.v2board",
    r"window\.xboard",
    r"/static/js/main\.js",
    r"v2board-config",
    r"v2board-auth"
]

async def check_target(session, ip, port):
    """单次探测逻辑"""
    protocol = "https" if port in [443, 8443] else "http"
    url = f"{protocol}://{ip}:{port}"
    
    # 随机微小延迟，打乱流量特征
    await asyncio.sleep(random.uniform(0.1, 0.5))
    
    try:
        async with session.get(url, timeout=TIMEOUT, allow_redirects=True, ssl=False) as response:
            if response.status != 200:
                return None
                
            content = await response.text()
            
            # 命中检测
            hits = [fp for fp in FINGERPRINTS if re.search(fp, content, re.IGNORECASE)]
            
            if hits:
                print(f"✨ [Found] {url} | Hits: {len(hits)}")
                return {
                    "url": url,
                    "ip": ip,
                    "port": port,
                    "fingerprints": "|".join(hits),
                    "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
    except Exception:
        pass
    return None

async def main():
    network = ipaddress.ip_network(TARGET_NETWORK)
    hosts = list(network.hosts())
    
    # 使用 TCPConnector 限制并发连接数
    connector = aiohttp.TCPConnector(limit=CONCURRENT_LIMIT, ssl=False)
    
    print(f"🚀 开始安全扫描 {TARGET_NETWORK}...")
    print(f"📊 目标总数: {len(hosts) * len(PORTS)} 个探测点 | 并发限制: {CONCURRENT_LIMIT}")

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for ip in hosts:
            for port in PORTS:
                tasks.append(check_target(session, str(ip), port))
        
        # 使用 gather 并行执行，并过滤结果
        results = await asyncio.gather(*tasks)
        found_sites = [r for r in results if r]
        
        # 结果处理
        if found_sites:
            df = pd.DataFrame(found_sites)
            df.to_csv("v2board_results.csv", index=False, encoding='utf-8-sig')
            print(f"✅ 任务完成！共发现 {len(found_sites)} 个匹配站点。")
        else:
            # 创建一个空文件防止 Git Add 报错
            with open("v2board_results.csv", "w") as f:
                f.write("url,ip,port,fingerprints,scan_time\n")
            print("⚠️ 扫描结束，未发现匹配目标。")

if __name__ == "__main__":
    asyncio.run(main())
