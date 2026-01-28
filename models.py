"""
models.py

SQLAlchemy モデル定義
"""

from sqlalchemy import Column, Integer, Text, DateTime
from sqlalchemy.sql import func
from database import Base


class Intake(Base):
    """
    AIヒアリングナビの入力内容を保存するテーブル
    
    - id: 自動採番の主キー
    - payload: JSON文字列（入力内容をそのまま保存）
    - created_at: 作成日時
    """
    __tablename__ = "intakes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
