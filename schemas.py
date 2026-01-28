"""
schemas.py

FastAPI のレスポンス用スキーマ定義
（DBモデルとは役割を分離する）
"""

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class AdminIntakeSummary(BaseModel):
    """
    管理者向け summary（ルールベース）

    ・文章化しない
    ・重要情報のみを構造化
    ・CSV / PDF / 将来AIの材料として使う
    """

    # ① 主訴・症状
    chief_complaints: List[str] = []      # 例: ["腰痛", "首こり"]
    symptom_duration: Optional[str] = None  # 例: "3ヶ月以上"

    # ② 危険・注意サイン（最優先）
    red_flags: List[str] = []              # 例: ["しびれあり", "夜間痛あり"]

    # ③ 自律神経・生活影響
    sleep_trouble: Optional[bool] = None
    stress_level: Optional[str] = None     # low / middle / high

    # ④ 施術者向け即判断用メモ（非AI）
    clinical_focus: Optional[str] = None


class AdminIntakeDetailResponse(BaseModel):
    """
    /admin/intakes/{id} 用レスポンス

    ・raw: 保存された入力内容（dict）
    ・summary: 管理者向け summary
    """

    id: int
    raw: dict
    summary: AdminIntakeSummary
    created_at: datetime
