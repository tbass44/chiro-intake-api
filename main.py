from dotenv import load_dotenv
load_dotenv(override=True)

import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json
import secrets

from database import engine, get_db, init_db
from models import Intake
from schemas import AdminIntakeDetailResponse, AdminIntakeListItem, AdminIntakeListSummary
from summary import (
    build_admin_summary,
    build_user_ai_input,
    generate_overview_ai_text,
    generate_line_detail_ai_text,
)
from services.line import send_line_detail_if_enabled
from services.line_budget import can_send_line
from services.line_sender import send_line_message, send_line_initial_reply
from datetime import datetime, timezone

import csv
from io import StringIO


app = FastAPI()

# データベースとテーブルを作成
init_db()

# CORS 設定（本番 + ローカル対応）
origins = [
    "https://hearing.chiroshiga.com",
    "http://localhost:3000",
    "http://localhost:3001",
]

# CORS 設定（Next.js localhost からのリクエストを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
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
            content={
                "status": "ok",
                "intake_id": intake.id,
            }
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
    ・一覧表示用の最小 summary（red_flags / clinical_focus）    
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

            # 管理者向け summary を生成（既存ロジックを再利用）
            full_summary = build_admin_summary(payload_dict)

            # 一覧表示に必要な最小 summary だけを抜き出す
            list_summary = {
                "chief_complaints": full_summary.chief_complaints,
                "red_flags": full_summary.red_flags,
                "clinical_focus": full_summary.clinical_focus,
            }

            line_status = "連携済" if intake.line_user_id else "未連携"
            
            result.append({
                "id": intake.id,
                "payload": payload_dict,
                "created_at": intake.created_at.isoformat() if intake.created_at else None, # type: ignore[attr-defined]
                "summary": list_summary,
                "line_status": line_status,
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
            payload_dict = json.loads(intake.payload)
        except json.JSONDecodeError:
            payload_dict = {}

        # 管理者向け summary を生成
        summary = build_admin_summary(payload_dict)

        line_status = "連携済" if intake.line_user_id else "未連携"

        return {
            "id": intake.id,
            "raw": payload_dict,
            "summary": summary,
            "overview_text": intake.overview_text,
            "line_detail_text": intake.line_detail_text,
            "created_at": intake.created_at,  # type: ignore[attr-defined]
            "line_status": line_status,
            "line_sent_at": intake.line_sent_at,
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
    ・一覧用 summary を CSV 列として追加
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
            "name",
            "chief_complaint",      
            "line_status",      
            "has_red_flags",
            "red_flags",
            "clinical_focus",
            "stress_level",
            "sleep_trouble",
        ])

        for intake in intakes:
            # payload は DB では「JSON文字列」
            # → Python で扱いやすい dict に戻す
            try:
                payload_dict = json.loads(intake.payload)  # type: ignore[attr-defined]
            except json.JSONDecodeError:
                payload_dict = {}

            # summary を生成
            summary = build_admin_summary(payload_dict)

            # --- 主訴の取得 ---
            # symptoms[0].symptom を CSV 用に抜き出す
            chief = ""
            symptoms = payload_dict.get("symptoms", [])
            if isinstance(symptoms, list) and symptoms:
                chief = symptoms[0].get("symptom", "")

            line_status = "連携済" if intake.line_user_id else "未連携"

            # 1行分を書き込み
            writer.writerow([
                intake.id,
                intake.created_at.isoformat() if intake.created_at else "",  # type: ignore[attr-defined]
                payload_dict.get("name", ""),
                chief,
                line_status,

                # --- summary 展開 三項演算子 ---
                "YES" if summary.red_flags else "NO",
                " / ".join(summary.red_flags),
                summary.clinical_focus or "",
                summary.stress_level or "",
                "YES" if summary.sleep_trouble else "NO",
            ])

        # --- CSV を HTTP レスポンスとして返す ---
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

# ============================================================
# ユーザー向けAI要約用の「材料」を返す API
# ============================================================
from summary import build_user_ai_input


@app.get("/api/intake/{id}/user-summary")
async def get_user_summary_material(
    id: int,
    db: Session = Depends(get_db)
):
    """
    【このエンドポイントの役割】

    ・指定された intake ID の入力内容を取得
    ・管理者向け summary を生成（判断）
    ・ユーザー向けAI要約の材料を作成
    ・概要AI要約 / LINE詳細AI要約 を生成
    ・DBに保存
    ・概要だけを返す（送信完了画面用）
    """    

    try:
        # ----------------------------------------
        # ① DB から intake を取得
        # ----------------------------------------
        intake = db.query(Intake).filter(Intake.id == id).first()
        if intake is None:
            raise HTTPException(status_code=404, detail="Not found")

        # ----------------------------------------
        # ② payload（JSON文字列）を dict に戻す
        # ----------------------------------------
        try:
            payload_dict = json.loads(intake.payload)
        except json.JSONDecodeError:
            payload_dict = {}

        # ----------------------------------------
        # ③ 管理者向け summary を生成
        # ----------------------------------------
        admin_summary = build_admin_summary(payload_dict)

        # ----------------------------------------
        # ④ ユーザー向けAI要約の材料を生成
        # ----------------------------------------
        user_ai_input = build_user_ai_input(admin_summary)

        # ----------------------------------------
        # ⑤ AI要約を生成（上限ガード付き）
        # ----------------------------------------
        overview_text = generate_overview_ai_text(user_ai_input)
        line_detail_text = generate_line_detail_ai_text(user_ai_input)

        # ----------------------------------------
        # LINE連携トークンを発行
        # ----------------------------------------
        if not intake.line_link_token:
            intake.line_link_token = secrets.token_urlsafe(16)

        # ----------------------------------------
        # ⑥ DB に保存
        # ----------------------------------------
        intake.overview_text = overview_text
        intake.line_detail_text = line_detail_text
        db.commit()

        # ----------------------------------------
        # ⑥.5 LINE送信（スイッチ付き）
        # ----------------------------------------
        send_line_detail_if_enabled(
            intake_id=intake.id,
            line_detail_text=line_detail_text,
        )

        # ----------------------------------------
        # ⑦ 概要だけ返す（完了画面用）
        # ----------------------------------------
        return {
            "overview": overview_text,
            "line_link_token": intake.line_link_token,  # ← フロントで使う
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/webhook/line")
async def line_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    LINE Webhook（受信専用・DRY RUN）

    期待：
    - 友だち追加 or 最初のメッセージ
    - text に 'link=xxxxx' が含まれる
    """
    raw_body = await request.body()

    # 🔹 LINE Verify 用（bodyが空）
    if not raw_body:
        return {"status": "ok"}

    # 🔹 ここから通常処理
    payload = await request.json()

    # ↓ ここから先で JSON parse & 本処理

    try:
        print("[LINE] webhook received")
        print(payload)

        events = payload.get("events", [])
        if not events:
            return {"status": "ok"}

        event = events[0]
        source = event.get("source", {})
        line_user_id = source.get("userId")

        message = event.get("message", {})
        text = message.get("text", "")

        # link=TOKEN を抜き出す
        token = None
        if "link=" in text:
            token = text.split("link=", 1)[1].strip()

        if not token:
            print("[LINE] no token")
            return {"status": "ok"}

        intake = db.query(Intake).filter(Intake.line_link_token == token).first()
        if not intake:
            print("[LINE] token not found")
            return {"status": "ok"}

        # すでに送信済みなら何もしない
        if intake.line_sent_at:
            print("[LINE] already sent")
            return {"status": "ok"}


        # --- ここからが「実送信切替」 ---

        # ① 送信スイッチ
        if os.getenv("LINE_SEND_ENABLED", "false").lower() != "true":
            print("[LINE] send disabled by env")
            return {"status": "ok"}

        now = datetime.now(timezone.utc)

        # ② 予算ガード
        if not can_send_line(now):
            print("[LINE] budget exceeded")
            return {"status": "ok"}

        # ③ 実送信
        # ③-1 初回自動返信（固定文）
        send_line_initial_reply(
            line_user_id=line_user_id,
        )

        # ③-2 AI要約（詳細）
        send_line_message(
            line_user_id=line_user_id,
            text=intake.line_detail_text or "",
        )

        # ④ 送信成功したら確定
        intake.line_user_id = line_user_id
        intake.line_sent_at = now
        db.commit()

        print("===================================")
        print("[LINE] SENT")
        print(f"intake_id: {intake.id}")
        print(f"line_user_id: {line_user_id}")
        print("===================================")

        return {"status": "ok"}

    except Exception as e:
        # 失敗時は commit しない（＝再送されない安全設計）
        print(f"[LINE] webhook error: {e}")
        return {"status": "ok"}

# 再送エンドポイント
@app.post("/admin/intakes/{id}/resend-line")
async def resend_line_message(
    id: int,
    db: Session = Depends(get_db),
):
    """
    管理者用：LINE再送信
    ・未連携の intake のみ対象
    ・既存の送信ガードをすべて適用
    """

    intake = db.query(Intake).filter(Intake.id == id).first()
    if intake is None:
        raise HTTPException(status_code=404, detail="Not found")

    # すでに連携済みなら送らない
    if intake.line_user_id:
        return {"status": "already_linked"}

    if not intake.line_link_token:
        return {"status": "no_link_token"}

    # --- 送信スイッチ ---
    if os.getenv("LINE_SEND_ENABLED", "false").lower() != "true":
        return {"status": "send_disabled"}

    now = datetime.now(timezone.utc)

    # --- 予算ガード ---
    if not can_send_line(now):
        return {"status": "budget_exceeded"}

    # ❗ userId が無いので「送信」はできない
    # 👉 ここでは「再案内メッセージ」を送る設計にする
    # （link=xxxx を再度送ってもらう用）

    return {
        "status": "need_user_action",
        "message": "LINEで link=XXXX を再送してもらってください"
    }
