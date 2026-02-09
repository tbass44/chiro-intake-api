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
