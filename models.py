"""
models.py

SQLAlchemy モデル定義
"""

from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, Text, func
from database import Base


class Intake(Base):
    """
    AIヒアリングナビの入力内容を保存するテーブル

    - id: 自動採番の主キー
    - payload: JSON文字列（入力内容をそのまま保存）
    - overview_text: ユーザー向け概要AI要約（送信完了画面用）
    - line_detail_text: LINE送信用の詳細AI要約（※まだ送信しない）
    - created_at: 作成日時
    """
    __tablename__ = "intakes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # フロントから送られてきた生データ
    payload: Mapped[str] = mapped_column(Text, nullable=False)

    # --- AI生成テキスト（後付け） ---
    overview_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_detail_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # LINE連携
    line_link_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Pythonの datetime を型にする
    line_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
