import os
from google import genai

API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

print("利用可能なモデル一覧を取得中...")

# 利用可能なモデルをリストアップ
for model in client.models.list():
    # 最新の仕様である 'supported_actions' を使用して、テキスト生成に対応しているか判定
    # APIの仕様変更に備え、属性の存在チェックを挟んでいます
    actions = getattr(model, 'supported_actions', [])
    
    if "generateContent" in actions:
        # モデル名（例: 'models/gemini-2.5-flash'）を表示
        print(f"Model Name: {model.name}")
        if hasattr(model, 'description') and model.description:
            print(f"  └ Description: {model.description}\n")