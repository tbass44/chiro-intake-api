from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json

from database import engine, get_db, init_db
from models import Intake

app = FastAPI()

# データベースとテーブルを作成
init_db()

# CORS 設定（Next.js localhost からのリクエストを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.post("/api/intake")
async def receive_intake(request: Request):
    """
    AIヒアリングナビの入力内容を受け取るエンドポイント
    
    ・リクエストボディは JSON をそのまま受け取る
    ・受け取った内容をログ出力
    ・SQLite に保存
    ・正常時は 200 OK と { "status": "ok" } を返す
    """
    db: Session = next(get_db())
    try:
        # リクエストボディを JSON として取得
        body = await request.json()
        
        # 受け取った内容をログ出力
        print("=" * 50)
        print("AIヒアリングナビ 入力内容を受信")
        print("=" * 50)
        print(json.dumps(body, ensure_ascii=False, indent=2))
        print("=" * 50)
        
        # JSON を文字列化して payload に保存
        payload_str = json.dumps(body, ensure_ascii=False)
        
        # データベースに保存
        intake = Intake(payload=payload_str)
        db.add(intake)
        db.commit()
        db.refresh(intake)
        
        print(f"データベースに保存しました (ID: {intake.id})")
        
        # 正常レスポンス
        return JSONResponse(
            status_code=200,
            content={"status": "ok"}
        )
        
    except json.JSONDecodeError:
        # JSON パースエラー
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON format"
        )
    except Exception as e:
        # その他のエラー
        db.rollback()
        print(f"Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
    finally:
        db.close()


@app.get("/admin/intakes")
async def get_intakes():
    """
    AIヒアリングナビの入力データを一覧取得するエンドポイント
    
    ・SQLite の intakes テーブルから全件取得
    ・取得項目は id, payload, created_at
    ・payload は JSON 文字列を dict に変換して返す
    ・created_at の降順で並べる（新しい順）
    ・レスポンスは JSON 配列で返す
    """
    db: Session = next(get_db())
    try:
        # データベースから全件取得（created_at 降順）
        intakes = db.query(Intake).order_by(desc(Intake.created_at)).all()
        
        # レスポンス用の配列を作成
        result = []
        for intake in intakes:
            # payload を JSON 文字列から dict に変換
            try:
                payload_dict = json.loads(intake.payload)
            except json.JSONDecodeError:
                # JSON パースエラーの場合は空の dict にする
                payload_dict = {}
            
            result.append({
                "id": intake.id,
                "payload": payload_dict,
                "created_at": intake.created_at.isoformat() if intake.created_at else None
            })
        
        # JSON 配列で返す
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except Exception as e:
        # エラー時は 500 を返す
        print(f"Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
    finally:
        db.close()


@app.get("/admin/intakes/{id}")
async def get_intake(id: int):
    """
    AIヒアリングナビの入力データを ID 指定で1件取得するエンドポイント

    ・SQLite の intakes テーブルから指定 ID の1件を取得
    ・取得項目は id, payload, created_at
    ・payload は JSON 文字列を dict に変換して返す
    ・該当レコードが存在しない場合は 404 を返す
    ・レスポンスは JSON オブジェクトで返す
    """
    db: Session = next(get_db())
    try:
        intake = db.query(Intake).filter(Intake.id == id).first()
        if intake is None:
            raise HTTPException(status_code=404, detail="Not found")

        try:
            payload_dict = json.loads(intake.payload)
        except json.JSONDecodeError:
            payload_dict = {}

        return JSONResponse(
            status_code=200,
            content={
                "id": intake.id,
                "payload": payload_dict,
                "created_at": intake.created_at.isoformat() if intake.created_at else None,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        db.close()
