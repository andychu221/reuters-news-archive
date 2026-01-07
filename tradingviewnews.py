import requests
import json
from datetime import datetime
import time
from zoneinfo import ZoneInfo
taipei_tz = ZoneInfo("Asia/Taipei")

def fetch_reuters_morning_news():
    # TradingView 新聞 API
    api_url = "https://news-headlines.tradingview.com/v2/headlines"

    configs_to_try = [
        {"client": "web", 'lang': 'zh-Hant',"provider": "reuters"},
        {"client": "web", "lang": "en","provider": "reuters"},
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://tw.tradingview.com",
        "Referer": "https://tw.tradingview.com",
    }

    successful_items = []

    print("正在嘗試連接 API...\n")

    for i, params in enumerate(configs_to_try, 1):
        try:
            print(f"[{i}/{len(configs_to_try)}] 測試參數: {params}")
            response = requests.get(api_url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])

                if items:
                    print(f"-> 成功! (狀態碼: 200，取得 {len(items)} 筆資料)")
                    successful_items = items
                    break
                else:
                    print(f"-> 連線成功 (200) 但回傳資料為空。")
            else:
                print(f"-> 失敗 (狀態碼: {response.status_code})")

            time.sleep(1)
        except Exception as e:
            print(f"-> 發生錯誤: {e}")

    if not successful_items:
        print("\n[錯誤] 無法取得任何新聞資料。")
        return

    filter_keywords = [
       "路透早報",
       "全球匯市",
       "全球股市",
       "全球主要債市",
       "全球主要外匯市場"
    ]

    print(f"\n取得 {len(successful_items)} 筆資料,正在篩選包含以下關鍵字的新聞:")
    print(f"關鍵字: {', '.join(filter_keywords)}\n")
    print("-" * 50)

    found_count = 0

    for item in successful_items:
        title = item.get("title", "")
        provider = item.get("provider", "").lower()
        title_lower = title.lower()

        # 篩選條件：標題含有 "路透"
        if any(keyword.lower() in title_lower for keyword in filter_keywords):
          news_id = item.get("id", "")

          # 處理連結
          if item.get("storyPath"):
              link_path = item.get("storyPath")
          else:
              link_path = f"/news/{news_id}/"

          if not link_path.startswith("/"):
              link_path = "/" + link_path

          full_url = f"https://tw.tradingview.com{link_path}"

          # 時間戳記轉換
          published_ts = item.get("published", 0)
          utc_time = datetime.fromtimestamp(published_ts, tz=ZoneInfo("UTC"))
          taipei_time = utc_time.astimezone(taipei_tz)
          date_str = taipei_time.strftime('%Y-%m-%d %H:%M:%S %Z')

          print(f"標題: {title}")
          print(f"網址: {full_url}")
          print(f"時間: {date_str}")
          print("-" * 30)
          found_count += 1

    if found_count == 0:
        print(f"未發現包含關鍵字 {filter_keywords} 的新聞。")

if __name__ == "__main__":
    fetch_reuters_morning_news()
