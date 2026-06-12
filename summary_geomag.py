import os
import json
import ssl
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import feedparser
from google import genai
from google.genai.errors import APIError

# 1. 環境変数から各種キーを取得
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

if not GEMINI_API_KEY:
    raise ValueError("環境変数 'GEMINI_API_KEY' が設定されていません。")

# 最新のGenAIクライアントを初期化（内部タイムアウトのバグを避けるためデフォルト設定）
client = genai.Client(api_key=GEMINI_API_KEY)

# 地磁気・古地磁気・コアダイナモ物理の網羅キーワード
GEOMAG_KEYWORDS = [
    "geomagnetism", "paleomagnetism", "rock magnetism", "dynamo", 
    "outer core", "geodynamo", "dissipation", "convection", 
    "earth's core", "reversal", "dynamo model", "core flow", "magnetohydrodynamic"
]

def is_geomag_paper(title, summary):
    """タイトルまたはアブストラクトに地磁気関連のキーワードが含まれるか判定"""
    text = (title + " " + summary).lower()
    return any(keyword in text for keyword in GEOMAG_KEYWORDS)

def fetch_arxiv_data():
    """arXivから最新論文を取得"""
    query = '(cat:physics.geo-ph) AND (ti:geomagnetism OR ti:paleomagnetism OR ti:dynamo OR abs:geomagnetism OR abs:paleomagnetism OR abs:dynamo)'
    url = f'http://export.arxiv.org/api/query?search_query={urllib.parse.quote(query)}&sortBy=submittedDate&sortOrder=descending&max_results=2'
    
    try:
        with urllib.request.urlopen(url) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)
        
        papers = []
        for entry in entries:
            papers.append({
                'source': 'arXiv',
                'title': entry.find('atom:title', ns).text.strip().replace('\n', ' '),
                'summary': entry.find('atom:summary', ns).text.strip().replace('\n', ' '),
                'url': entry.find("atom:id", ns).text.strip()
            })
        return papers
    except Exception as e:
        print(f"   [Warning] arXivからのデータ取得に失敗しました: {e}")
        return []

def fetch_journal_data():
    """主要4ジャーナルのRSSフィードから最新論文を抽出（ブロック完全回避版）"""
    rss_feeds = {
        "JGR: Solid Earth": "https://agupubs.onlinelibrary.wiley.com/rss/journal/21699356",
        "EPSL": "https://rss.sciencedirect.com/publication/science/0012821X",
        "GJI": "https://academic.oup.com/rss/site_5282/advanceAccess_3148.xml",  # 発掘した真のURL
        "PEPI": "https://rss.sciencedirect.com/publication/science/00319201"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    # SSLエラーによる通信ブロックを回避
    context = ssl._create_unverified_context()
    papers = []
    
    for journal_name, url in rss_feeds.items():
        print(f"   {journal_name} のRSSをチェック中...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15, context=context) as response:
                xml_data = response.read()
                
            feed = feedparser.parse(xml_data)
            count = 0
            for entry in feed.entries:
                title = entry.get('title', '')
                summary = entry.get('summary', entry.get('description', ''))
                link = entry.get('link', '')
                
                if is_geomag_paper(title, summary):
                    papers.append({
                        'source': journal_name,
                        'title': title,
                        'summary': summary,
                        'url': link
                    })
                    count += 1
                    if count >= 2:
                        break
            print(f"   ➔ {journal_name} から地磁気関連を {count} 件抽出しました。")
        except Exception as e:
            print(f"   [Warning] {journal_name} のRSS取得中にエラーが発生しました: {e}")
            continue
            
    return papers

def analyze_paper_with_gemini(source, title, abstract):
    """Gemini 3.5-flash を使って翻訳・要約・重要度判定を実行"""
    prompt = f"""
あなたは地球科学（特に地磁気学、古地磁気学、岩石磁気学、地球流体力学・数値ダイナモシミュレーション）を専門とする高名な研究者です。
掲載元（ジャーナル名またはプレプリント名）の特性も考慮し、以下の論文のタイトルとアブストラクトを読み、日本の研究者や大学院生向けに以下のフォーマット（Markdown形式）で厳密かつ分かりやすく出力してください。

# 論文情報
【掲載元】: {source}
【タイトル（日本語訳）】: （ここに日本語訳を記述）
【重要度判定】: （A:必読、B:要チェック、C:参考程度 のいずれか1文字）
【重要度の理由】: （なぜその重要度と判定したのか、理論的・実験的ブレイクスルーの観点から1行で記述）

# 要約
（専門用語を省略せず、数式やダイナモ・熱塩対流などの物理メカニズム、実験手法の新規性がわかるように、箇条書きで3行で要約してください）

---
【対象論文】
Title: {title}
Abstract: {abstract}
"""
    
    model_priority = ['models/gemini-3.5-flash', 'models/gemini-2.5-flash']
    
    for model_name in model_priority:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            return response.text
        except APIError as e:
            print(f"   [Warning] {model_name} でエラーが発生しました (Status Code: {e.code})")
            continue
        except Exception as e:
            print(f"   [Warning] 予期せぬエラー: {e}")
            continue
            
    raise RuntimeError("すべての候補Geminiモデルで解析に失敗しました。")

def send_to_discord(content):
    if not DISCORD_WEBHOOK_URL:
        print("   [Info] DISCORD_WEBHOOK_URL が設定されていないため、画面出力のみ行います。")
        return
        
    payload = {"content": content}
    
    # 💡 Content-Type に加えて、ブラウザのフリをする User-Agent を追加
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    try:
        # SSLブロック対策のcontextも念のため適用
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=15, context=context) as response:
            pass
    except Exception as e:
        print(f"   [Warning] Discordへの通知に失敗しました: {e}")

def main():
    print("1. 論文データの収集を開始します...")
    arxiv_papers = fetch_arxiv_data()
    journal_papers = fetch_journal_data()
    
    all_papers = arxiv_papers + journal_papers
    print(f"\n➔ 合計 {len(all_papers)} 件の地磁気・コア関連論文を検出しました。")
    
    if not all_papers:
        print("新規論文はありませんでした。")
        return
        
    print("\n2. Gemini APIによる解析およびDiscordへの通知を開始します...")
    for i, paper in enumerate(all_papers, 1):
        print(f"   [{i}/{len(all_papers)}] 解析中: {paper['title'][:40]}...")
        
        try:
            analysis_result = analyze_paper_with_gemini(paper['source'], paper['title'], paper['summary'])
            
            # Discord送信用にテキストを整形（URLを上部に配置）
            discord_message = f"**【新着論文通知】**\nURL: {paper['url']}\n{analysis_result}"
            
            # Discordへ送信
            send_to_discord(discord_message)
            
            # ターミナル側にも確認用に出力
            print(analysis_result)
            print("-" * 40)
            
        except Exception as e:
            print(f"   [Error] 論文 [{i}] の処理中にエラーが発生しました: {e}")

if __name__ == "__main__":
    main()