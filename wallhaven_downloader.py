import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor

# ================= 配置区域 =================
API_KEY = "g145x8xSY1fbhFaeSMQSQbRTNWjST1Oh" # 已为您集成 API Key
SAVE_DIR = "wallhaven_toplist_lastmonth"    # 新建的保存目录
DOWNLOAD_COUNT = 10                         # 下载前 10 张
START_PAGE = 1                              # 从第一页开始
PURITY = "111"                             # 111 代表包含 SFW, Sketchy, NSFW
CATEGORIES = "111"                         # 111 代表 General, Anime, People
TOP_RANGE = "1M"                            # Last Month

# VPN 代理设置 (根据您的要求设置端口为 15235)
PROXIES = {
    "http": "socks5h://127.0.0.1:15235",
    "https": "socks5h://127.0.0.1:15235"
}
# ===========================================

def download_image(img_url, img_id):
    """下载单张原图"""
    try:
        ext = img_url.split('.')[-1]
        file_path = os.path.join(SAVE_DIR, f"{img_id}.{ext}")
        
        if os.path.exists(file_path):
            print(f"[跳过] {img_id} 已存在")
            return

        # 伪造请求头，防止被屏蔽
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        resp = requests.get(img_url, headers=headers, proxies=PROXIES, timeout=60)
        if resp.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(resp.content)
            print(f"[完成] 已下载 {img_id}")
        else:
            print(f"[错误] 下载 {img_id} 失败，状态码: {resp.status_code}")
    except Exception as e:
        print(f"[异常] 下载 {img_id} 出错: {e}")

def main():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    image_list = []
    page = START_PAGE
    
    print(f"正在获取图片列表 (从第 {START_PAGE} 页开始)...")
    
    while len(image_list) < DOWNLOAD_COUNT:
        # API 搜索接口
        url = "https://wallhaven.cc/api/v1/search"
        params = {
            'apikey': API_KEY,
            'sorting': 'toplist',
            'topRange': TOP_RANGE,
            'categories': CATEGORIES,
            'purity': PURITY,
            'page': page
        }
        
        try:
            resp = requests.get(url, params=params, proxies=PROXIES, timeout=15)
            data = resp.json()
            
            if resp.status_code != 200:
                print(f"API 请求失败: {data.get('error', '未知错误')}")
                break
                
            batch = data.get('data', [])
            if not batch:
                print("没有更多图片了。")
                break
                
            for img in batch:
                if len(image_list) >= DOWNLOAD_COUNT:
                    break
                # API 返回的 'path' 即为原图直链
                image_list.append((img['path'], img['id']))
            
            print(f"已扫描第 {page} 页，累计获取: {len(image_list)}/{DOWNLOAD_COUNT}")
            page += 1
            
            # 遵守 API 速率限制 (每分钟 45 次请求)
            time.sleep(1.5) 
            
        except Exception as e:
            print(f"获取列表出错: {e}")
            break

    if not image_list:
        print("未获取到任何图片，请检查 API Key 是否有效。")
        return

    print(f"\n开始并行下载 {len(image_list)} 张原图 (线程数: 5)...")
    
    # 使用多线程下载，既快又稳定
    with ThreadPoolExecutor(max_workers=5) as executor:
        for img_url, img_id in image_list:
            executor.submit(download_image, img_url, img_id)

    print(f"\n下载任务全部完成！图片保存在: {os.path.abspath(SAVE_DIR)}")

if __name__ == "__main__":
    main()
