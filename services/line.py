"""
services/line.py

LINE送信の入口（スイッチ付き）
※現時点では DRY RUN（ログ出力のみ）
"""

import os


def send_line_detail_if_enabled(*, intake_id: int, line_detail_text: str) -> None:
    """
    LINE送信スイッチ付きの入口関数

    ・LINE_SEND_ENABLED=false → 何もしない
    ・LINE_SEND_ENABLED=true  → 送信処理に入る（今はログのみ）

    将来ここを LINE Messaging API 呼び出しに差し替える。
    """
    enabled = os.getenv("LINE_SEND_ENABLED", "false").lower() == "true"

    if not enabled:
        print(f"[LINE] disabled. intake_id={intake_id}")
        return

    # まだ送らない：確認用ログ（DRY RUN）
    print("===================================")
    print("[LINE] SEND (DRY RUN)")
    print(f"intake_id: {intake_id}")
    print("message:")
    print(line_detail_text)
    print("===================================")
