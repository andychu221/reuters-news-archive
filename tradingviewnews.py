import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta, timezone
import time
import random
from github import Github
import base64
import re

# ============================================================
# 設定值
# ============================================================
# Google API 設定
GOOGLE_API_KEY = ""  # 填入你的 API Key
GOOGLE_CX = ""  # 填入你的 Custom Search Engine ID

# GitHub 設定
GITHUB_TOKEN = ""  # 填入你的 GitHub Personal Access Token
GITHUB_REPO = ""  # 填入格式：username/repository_name
GITHUB_FILE_PATH = "reuters_archive.json"  # JSON 檔案在 GitHub 的路徑

# 爬蟲設定
DEFAULT_DAYS = 5      # 如果是第一次執行，預設抓取的天數
MAX_SEARCH_RESULTS = 20 # 每個類別搜尋的結果數量
BASE_DELAY = 3        # 基礎延遲秒數
CATEGORY_DELAY = 5    # 每個類別處理後的延遲秒數

# 搜尋類別配置 (已簡化，所有類別都使用統一策略)
SEARCH_CATEGORIES = [
    {
        "name": "路透早報",
        "source": "TradingView - Reuters Morning Brief",
        "search_pattern": "《路透早報》",
        "title_keywords": ["路透早報"]
    },
    {
        "name": "全球匯市",
        "source": "TradingView - Global FX",
        "search_pattern": "全球匯市",
        "title_keywords": ["全球匯市"]
    },
    {
        "name": "美國債市",
        "source": "TradingView - US Bonds",
        "search_pattern": "美國債市",
        "title_keywords": ["美國債市"]
    },
    {
        "name": "台灣匯市",
        "source": "TradingView - Taiwan FX",
        "search_pattern": "台灣匯市",
        "title_keywords": ["台灣匯市"]
    },
    {
        "name": "台灣債市",
        "source": "TradingView - Taiwan Bonds",
        "search_pattern": "台灣債市",
        "title_keywords": ["台灣債市"]
    }
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

# ============================================================
# 檢查必要設定
# ============================================================
if not GOOGLE_API_KEY or not GOOGLE_CX:
    print("❌ 請填入 GOOGLE_API_KEY 和 GOOGLE_CX")
    exit(1)

if not GITHUB_TOKEN or not GITHUB_REPO:
    print("❌ 請填入 GITHUB_TOKEN 和 GITHUB_REPO")
    exit(1)

print("=" * 80)
print("TradingView 路透新聞爬蟲 - 終極簡化版")
print("=" * 80)

# ============================================================
# 連接 GitHub
# ============================================================
print("\n正在連接 GitHub...")
try:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
    print(f"✓ 已連接到儲存庫：{GITHUB_REPO}")
except Exception as e:
    print(f"❌ GitHub 連接失敗：{e}")
    exit(1)

# ============================================================
# 從 GitHub 讀取現有資料
# ============================================================
print("\n正在讀取 GitHub 上的存檔資料...")
existing_data = {"last_updated": "", "reports": []}
file_sha = None
existing_titles = set()

try:
    file_content = repo.get_contents(GITHUB_FILE_PATH)
    file_sha = file_content.sha
    content_text = base64.b64decode(file_content.content).decode('utf-8')
    existing_data = json.loads(content_text)
    # 建立現有標題的集合，用於快速比對
    existing_titles = {report.get('Title') for report in existing_data.get('reports', [])}
    print(f"✓ 找到存檔檔案，現有報導數：{len(existing_data.get('reports', []))} 篇")
except Exception as e:
    print(f"⚠️  讀取失敗（可能是第一次執行），將建立新檔案。")

# ============================================================
# 計算需要抓取的日期範圍
# ============================================================
today = datetime.now(timezone(timedelta(hours=8)))
last_updated_str = existing_data.get('last_updated', '')
days_to_scrape = DEFAULT_DAYS

if last_updated_str:
    try:
        last_date = datetime.strptime(last_updated_str, '%Y-%m-%d').replace(tzinfo=timezone(timedelta(hours=8)))
        days_diff = 20#(today - last_date).days
        if days_diff <= 0:
            print(f"\n✓ 資料已是最新（最後更新：{last_updated_str}）。")
            exit(0)
        days_to_scrape = days_diff if days_diff > 0 else 1
    except ValueError:
        print(f"⚠️ 無法解析上次更新日期，使用預設天數: {DEFAULT_DAYS} 天")

print(f"\n將搜尋過去 {days_to_scrape} 天內的新聞。")
print("=" * 80)

# ============================================================
# 輔助函數
# ============================================================
def extract_datetime_from_page(soup):
    """從頁面 <time> 標籤提取準確的 datetime 物件 (已轉換為 UTC+8)"""
    time_tag = soup.find('time', datetime=True)
    if time_tag and time_tag.get('datetime'):
        try:
            datetime_str = time_tag['datetime']
            dt_utc = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            dt_taipei = dt_utc.astimezone(timezone(timedelta(hours=8)))
            return dt_taipei
        except Exception:
            return None
    return None

def fetch_page_content(url):
    """抓取單一頁面的內容並解析"""
    time.sleep(BASE_DELAY + random.uniform(0, 2))
    headers = {'User-Agent': random.choice(USER_AGENTS), 'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        h1_title = soup.find('h1', class_=re.compile(r'title-'))
        page_title = h1_title.get_text(strip=True) if h1_title else "標題無法取得"

        content_div = soup.find('div', class_=re.compile(r'content-')) or soup.find('article')
        content = ""
        if content_div:
            for tag in content_div(['script', 'style', 'aside']):
                tag.decompose()
            content = content_div.get_text(separator='\n', strip=True)

        return page_title, content, soup
    except Exception as e:
        print(f"  └ 錯誤：抓取頁面 {url} 失敗 - {e}")
        return None, None, None

# ============================================================
# 主要爬取邏輯
# ============================================================
all_new_reports = []
api_call_count = 0

print("\n【開始執行搜尋任務】")
for category_index, category in enumerate(SEARCH_CATEGORIES, 1):
    print(f"\n--- [{category_index}/{len(SEARCH_CATEGORIES)}] 處理類別：{category['name']} ---")
    query = f"site:tw.tradingview.com/news/reuters.com/ \"{category['search_pattern']}\""

    print(f"  搜尋：{query}")
    api_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'key': GOOGLE_API_KEY, 'cx': GOOGLE_CX, 'q': query,
        'num': MAX_SEARCH_RESULTS, 'lr': 'lang_zh-TW',
        'sort': 'date', 'dateRestrict': f'd{days_to_scrape}'
    }

    try:
        api_call_count += 1
        print(f"  正在呼叫 Google API... (今日第 {api_call_count} 次)")
        time.sleep(CATEGORY_DELAY + random.uniform(0, 3))
        response = requests.get(api_url, params=params, timeout=20)
        response.raise_for_status()
        search_results = response.json().get('items', [])
        print(f"  ✓ 找到 {len(search_results)} 個結果")

        for item in search_results:
            url = item.get('link', '')
            google_title = item.get('title', '')
            print(f"\n  > 檢查: {google_title[:50]}...")

            if 'tw.tradingview.com/news/reuters.com' not in url:
                print("  └ 略過：非目標新聞連結")
                continue

            page_title, content, soup = fetch_page_content(url)
            if not all([page_title, content, soup]) or page_title == "標題無法取得":
                continue

            # **核心邏輯：直接比對標題是否已存在**
            if page_title in existing_titles:
                print("  └ 略過：報導標題已存在於 GitHub 存檔")
                continue

            if not any(keyword in page_title for keyword in category['title_keywords']):
                print(f"  └ 略過：標題不含關鍵字 {category['title_keywords']}")
                continue

            if len(content) < 100:
                print(f"  └ 略過：內容過短 ({len(content)} 字元)")
                continue

            article_datetime = extract_datetime_from_page(soup)
            if not article_datetime:
                print("  └ 警告：無法從頁面提取準確日期，將使用當前日期")
                article_datetime = today

            report_data = {
                "Source": category['source'], "URL": url,
                "Date": article_datetime.strftime('%Y-%m-%d'),
                "Time": article_datetime.strftime('%H:%M:%S'),
                "Title": page_title, "Content": content, "ContentLength": len(content),
                "ScrapedAt": today.strftime('%Y-%m-%d %H:%M:%S')
            }
            all_new_reports.append(report_data)
            existing_titles.add(page_title) # 新增至集合，避免本次執行重複抓取
            print(f"  ★★★★★ 成功加入新報導！★★★★★")

    except Exception as e:
        print(f"❌ 處理類別 {category['name']} 時發生錯誤：{e}")

# ============================================================
# 結果去重與統計
# ============================================================
print("\n" + "=" * 80)
print("抓取完成，進行最終處理...")
print("=" * 80)
print(f"API 總呼叫次數：{api_call_count}")

# 最終去重 (以防萬一)
unique_reports = []
seen_titles_final = set()
for report in all_new_reports:
    if report['Title'] not in seen_titles_final:
        unique_reports.append(report)
        seen_titles_final.add(report['Title'])

print(f"\n✓ 本次共新增：{len(unique_reports)} 篇")
if unique_reports:
    category_stats = {}
    for report in unique_reports:
        source = report['Source']
        category_stats[source] = category_stats.get(source, 0) + 1
    print("\n各類別統計：")
    for source, count in sorted(category_stats.items()):
        print(f"  {source}: {count} 篇")

# ============================================================
# 更新 GitHub 資料
# ============================================================
if unique_reports:
    print("\n" + "=" * 80)
    print("正在更新 GitHub 資料...")

    final_reports = existing_data.get('reports', []) + unique_reports
    final_reports.sort(key=lambda x: (x.get('Date', ''), x.get('Time', '')), reverse=True)

    updated_data = {
        "last_updated": today.strftime('%Y-%m-%d'),
        "total_reports": len(final_reports),
        "reports": final_reports
    }
    json_content = json.dumps(updated_data, ensure_ascii=False, indent=2)

    try:
        commit_message = f"新聞更新 {today.strftime('%Y-%m-%d')}：新增 {len(unique_reports)} 篇"
        if file_sha:
            repo.update_file(GITHUB_FILE_PATH, commit_message, json_content, file_sha)
            print(f"✓ 已更新 GitHub 檔案")
        else:
            repo.create_file(GITHUB_FILE_PATH, commit_message, json_content)
            print(f"✓ 已建立 GitHub 檔案")

        print("\n📋 本次新增的報導摘要：")
        for i, r in enumerate(sorted(unique_reports, key=lambda x: (x['Date'], x['Time'])), 1):
            print(f"{i}. [{r['Date']} {r['Time']}] {r['Title'][:50]}... ({r['Source']})")

    except Exception as e:
        print(f"❌ GitHub 更新失敗：{e}")
        backup_filename = f"reuters_backup_{today.strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_filename, 'w', encoding='utf-8') as f:
            f.write(json_content)
        print(f"✓ 已儲存本地備份：{backup_filename}")
else:
    print("\n⚠️  本次沒有新增任何報導，不更新 GitHub。")

print("\n" + "=" * 80)
print("程式執行完畢！")
print("=" * 80)

