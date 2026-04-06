# chiro-intake-api
整体院向け「AIヒアリングナビ」のバックエンドAPIです。  
フロントエンドから送信されたユーザー情報をもとに、データ処理およびレスポンス生成を行います。

## 技術スタック
- Python
- FastAPI
- SQLite

## 主な機能
- ユーザー入力データの受信・保存
- 条件に応じたレスポンス生成
- フロントエンドとのAPI連携
- LINE webhook連携（ユーザー入力取得）

## 工夫した点
- シンプルかつ拡張性の高いAPI設計
- SQLiteを用いた軽量なデータ管理（ローカル環境でも動作可能）
- フロントエンドとの連携を前提としたレスポンス設計
- webhookを活用した外部サービス連携
- AIツールとの連携を見据えた構成

## 起動手順
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

## 最終動作確認（1分）

### ① uvicorn 起動中を確認
### ② 管理画面API
### LINE webhook

curl http://localhost:8000/admin/intakes

curl -X POST http://localhost:8000/webhook/line \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "source": { "userId": "U_TEST_USER" },
        "message": { "text": "link=ZXa8DJzdv8cmtpLVTtPWZA" }
      }
    ]
  }'

## 管理画面API
curl http://localhost:8000/admin/intakes
