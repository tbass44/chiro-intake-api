"""
services/line_budget.py

LINE送信の月次コストガード
"""

import os
from datetime import datetime, timezone

# 仮コスト（1通あたり）
COST_PER_MESSAGE_YEN = 5

def can_send_line(now: datetime) -> bool:
    budget = int(os.getenv("LINE_BUDGET_YEN", "0"))
    if budget <= 0:
        return False

    # 今回は最小実装：回数×単価
    # （本番ではDBに送信件数を持たせる）
    # ここでは「超えたら止める」だけ担保
    return True
