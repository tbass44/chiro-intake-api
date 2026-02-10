# chiro-intake-api

## 起動手順

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

## 最終動作確認（1分）

### ① uvicorn 起動中を確認
### ② 管理画面API

### LINE webhook
```bash
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
