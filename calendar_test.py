# calendar_test.py - GoogleカレンダーAPIの接続テストプログラム
import datetime
import os.path
import sys
import io

# Windows環境での文字コードエラー対策
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# カレンダーの読み書き権限スコープ
SCOPES = ['https://www.googleapis.com/auth/calendar']

def main():
    creds = None
    
    # 1. すでに認証済みのトークンファイル (token.json) があるか確認
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    # 2. 認証情報がない、または有効期限切れの場合
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # credentials.json を元にブラウザ認証フローを開始
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # 次回以降のために認証情報を token.json として保存
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        # 3. Googleカレンダーサービスをビルド（初期化）
        service = build('calendar', 'v3', credentials=creds)

        # 4. テストとして、自分のカレンダーから直近の予定を5件取得してみる
        print('--- Googleカレンダーへの接続に成功しました ---')
        print('【あなたのGoogleカレンダー 直近の予定（最大5件）】')
        
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(
            calendarId='primary', 
            timeMin=now,
            maxResults=5, 
            singleEvents=True,
            orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            print('直近の予定は見つかりませんでした。')
        else:
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                print(f"- {start} : {event.get('summary')}")
                
        print('---------------------------------------------')

    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == '__main__':
    main()