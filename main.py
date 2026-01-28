from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json

from database import engine, get_db, init_db
from models import Intake
from schemas import AdminIntakeDetailResponse
from summary import build_admin_summary

import csv
from io import StringIO


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
                payload_dict = json.loads(intake.payload) # type: ignore[attr-defined]
            except json.JSONDecodeError:
                # JSON パースエラーの場合は空の dict にする
                payload_dict = {}
            
            result.append({
                "id": intake.id,
                "payload": payload_dict,
                "created_at": intake.created_at.isoformat() if intake.created_at else None # type: ignore[attr-defined]
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


@app.get("/admin/intakes/{id}", response_model=AdminIntakeDetailResponse)
async def get_intake(id: int, db: Session = Depends(get_db)):
    """
    AIヒアリングナビの入力データを ID 指定で1件取得（管理者用）

    ・raw payload（dict）
    ・管理者向け summary を追加
    """
    try:
        intake = db.query(Intake).filter(Intake.id == id).first()
        if intake is None:
            raise HTTPException(status_code=404, detail="Not found")

        # payload は JSON 文字列なので dict に変換
        try:
            payload_dict = json.loads(intake.payload)  # type: ignore[attr-defined]
        except json.JSONDecodeError:
            payload_dict = {}

        # 管理者向け summary を生成
        summary = build_admin_summary(payload_dict)

        return {
            "id": intake.id,
            "raw": payload_dict,
            "summary": summary,
            "created_at": intake.created_at,  # type: ignore[attr-defined]
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        db.close()

@app.get("/admin/intakes.csv")
async def export_intakes_csv(db: Session = Depends(get_db)):
    """
    管理者向け intake 一覧を CSV で出力するエンドポイント

    ・全 intake を取得
    ・payload から summary を生成
    ・1行 = 1 intake
    ・Excel で開ける UTF-8 CSV
    """

    try:
        # DB から全件取得（新しい順）
        intakes = db.query(Intake).order_by(desc(Intake.created_at)).all()

        # CSV をメモリ上で作成
        output = StringIO()
        writer = csv.writer(output)

        # ヘッダー行
        writer.writerow([
            "id",
            "created_at",
            "main_complaints",
            "symptom_duration",
            "sleep_trouble",
            "stress_level",
            "red_flags",
        ])

        for intake in intakes:
            # payload は JSON 文字列 → dict
            try:
                payload_dict = json.loads(intake.payload)  # type: ignore[attr-defined]
            except json.JSONDecodeError:
                payload_dict = {}

            # summary を生成
            summary = build_admin_summary(payload_dict)

            # 1行分を書き込み
            writer.writerow([
                intake.id,
                intake.created_at.isoformat() if intake.created_at else "",  # type: ignore[attr-defined]
                ",".join(summary.chief_complaints),
                summary.symptom_duration or "",
                summary.sleep_trouble,
                summary.stress_level or "",
                ",".join(summary.red_flags),
            ])

        # CSV をレスポンスとして返す
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=intakes.csv"
            },
        )

    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        db.close()
