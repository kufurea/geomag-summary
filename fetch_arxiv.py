import urllib.request
import xml.etree.ElementTree as ET

def fetch_geomag_papers():
    # 検索クエリの作成
    # physics:geo-ph (地球物理) カテゴリの中で、地磁気・古地磁気・ダイナモ関連の単語を検索
    query = '(cat:physics.geo-ph) AND (ti:geomagnetism OR ti:paleomagnetism OR ti:dynamo OR abs:geomagnetism OR abs:paleomagnetism OR abs:dynamo)'
    
    # arXiv APIのURLを構築（最新順に5件取得）
    url = f'http://export.arxiv.org/api/query?search_query={urllib.parse.quote(query)}&sortBy=submittedDate&sortOrder=descending&max_results=5'
    
    print("arXivから論文を取得中...")
    try:
        with urllib.request.urlopen(url) as response:
            xml_data = response.read()
    except Exception as e:
        print(f"データの取得に失敗しました: {e}")
        return

    # XMLの解析
    root = ET.fromstring(xml_data)
    
    # XMLのネームスペース（名前空間）の定義
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    
    # 各論文（entryタグ）の情報を抽出して表示
    entries = root.findall('atom:entry', ns)
    if not entries:
        print("該当する論文が見つかりませんでした。")
        return

    for i, entry in enumerate(entries, 1):
        title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
        summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
        url_link = entry.find("atom:id", ns).text.strip()
        
        print(f"\n--- 論文 [{i}] ---")
        print(f"【タイトル】: {title}")
        print(f"【URL】: {url_link}")
        print(f"【Abstract（冒頭100文字）】: {summary[:100]}...")

if __name__ == "__main__":
    fetch_geomag_papers()