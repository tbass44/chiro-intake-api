"""
services/line_sender.py

LINE Messaging API 実送信
"""

import os
import requests

LINE_API_URL = "https://api.line.me/v2/bot/message/push"

def send_line_message(*, line_user_id: str, text: str) -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN not set")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "to": line_user_id,
        "messages": [
            {
                "type": "text",
                "text": text,
            }
        ],
    }

    res = requests.post(LINE_API_URL, headers=headers, json=payload, timeout=5)

    if res.status_code >= 400:
        raise RuntimeError(f"LINE send failed: {res.status_code} {res.text}")

def send_line_initial_reply(*, line_user_id: str) -> None:
    """
    LINE 初回自動返信（固定文）
    link= トークン受信後、最初に1回だけ送る
    """

    initial_text = (
        "ご連絡ありがとうございます。\n"
        "カイロシガ整体院です。\n\n"
        "先ほどお送りいただいた内容をもとに、\n"
        "ヒアリング内容をLINEにお届けします。\n\n"
        "※この内容は診断や治療方針を決めるものではなく、\n"
        "来院時のカウンセリングをスムーズにするための整理情報です。\n\n"
        "ご不明な点があれば、このままLINEでご質問ください。"
    )

    send_line_message(
        line_user_id=line_user_id,
        text=initial_text,
    )
