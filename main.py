# main.py - 議事録からGeminiでタスクを抽出し、それぞれの期日にGoogleカレンダーへ自動登録するプログラム
import sys
import io
import os
import json

# Windows環境での文字コードエラー対策
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 外部環境変数 (.env) を読み込むためのライブラリ
from dotenv import load_dotenv

from google import genai
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ==========================================
# 外部設定ファイル (.env) の読み込み
# ==========================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
INPUT_FILE = os.getenv("INPUT_FILE", "input.txt")  # 設定がない場合のデフォルト値

# GoogleカレンダーAPIのスコープ（固定値）
SCOPES = ['https://www.googleapis.com/auth/calendar']


def get_calendar_service():
    """GoogleカレンダーのOAuth認証を行い、APIサービスオブジェクトを返す"""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('calendar', 'v3', credentials=creds)


def main():
    print("=== minutes-to-calendar 起動 ===")
    
    # APIキーの存在チェック
    if not GEMINI_API_KEY or GEMINI_API_KEY == "ここに取得したGeminiのAPIキーを貼り付け":
        print("❌ エラー: GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。")
        input("終了するには Enter キーを押してください...")
        return

    # 1. 議事録ファイルの存在チェック & 読み込み
    if not os.path.exists(INPUT_FILE):
        print(f"❌ エラー: 入力ファイル '{INPUT_FILE}' が見つかりません。実行ファイルと同じ場所に配置してください。")
        input("終了するには Enter キーを押してください...")
        return

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            minutes_text = f.read()
        print(f"--- 1. '{INPUT_FILE}' の読み込みに成功しました ---")
    except Exception as e:
        print(f"❌ ファイル読み込みエラー: {e}")
        return

    # 2. Gemini API連携 & タスク抽出
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
以下の議事録テキストから、今後発生する「タスク（アクションアイテム）」を抽出し、必ず以下のJSON配列フォーマットのみで出力してください。
マークダウンの記法（```json など）や、前後の余計な挨拶・説明文は一切含めないでください。

[
  {{
    "task": "タスク名（担当者名などを含む）",
    "datetime": "YYYY-MM-DD または YYYY-MM-DDTHH:MM:SS"
  }}
]

--- 議事録本文 ---
{minutes_text}
"""
        print("--- 2. Gemini API (gemini-3.8-flash) でタスクを構造化抽出中... ---")
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )
    except Exception as e:
        print(f"❌ Gemini API通信エラー（サーバー混雑またはネットワーク異常の可能性があります）: {e}")
        input("終了するには Enter キーを押してください...")
        return

    # レスポンスのクレンジング処理
    raw_response = response.text.strip()
    if raw_response.startswith("```"):
        raw_response = raw_response.split("```")[1]
        if raw_response.startswith("json"):
            raw_response = raw_response[4:]
    raw_response = raw_response.strip()

    print("\n【Gemini抽出JSON】")
    print(raw_response)
    print("-------------------------------------")

    # 3. JSONパース（例外設計）
    try:
        tasks = json.loads(raw_response)
    except json.JSONDecodeError as jde:
        print(f"❌ JSONパースエラー: AIの出力形式が不正です。再実行してください。\n詳細: {jde}")
        input("終了するには Enter キーを押してください...")
        return

    # 4. Googleカレンダーへ各タスクを個別に登録
    try:
        print("--- 3. Googleカレンダーへ各タスクを登録中... ---")
        service = get_calendar_service()

        success_count = 0
        for item in tasks:
            task_name = item.get("task")
            task_date = item.get("datetime")

            # 期日が指定されていない (null / None) 場合の例外ハンドリング
            if not task_date:
                print(f"⚠️ 期日未設定のためスキップしました: {task_name}")
                continue

            # 日時の形式に応じたイベント作成
            if "T" in str(task_date):
                start_time = task_date + ":00" if len(task_date) == 16 else task_date
                event_body = {
                    'summary': f"[タスク] {task_name}",
                    'start': {'dateTime': start_time, 'timeZone': 'Asia/Tokyo'},
                    'end': {'dateTime': start_time, 'timeZone': 'Asia/Tokyo'},
                }
            else:
                event_body = {
                    'summary': f"[タスク] {task_name}",
                    'start': {'date': task_date},
                    'end': {'date': task_date},
                }

            service.events().insert(calendarId='primary', body=event_body).execute()
            print(f"✅ 登録完了: {task_name} ({task_date})")
            success_count += 1

        print(f"\n🎉 処理完了: 成功 {success_count} 件 / 総タスク {len(tasks)} 件")

    except Exception as e:
        print(f"❌ GoogleカレンダーAPI登録エラー: {e}")

    input("\nすべての処理が終了しました。Enter キーを押すと終了します...")

if __name__ == '__main__':
    main()