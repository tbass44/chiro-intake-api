"""
database.py

SQLite データベース接続とセッション管理
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# SQLite データベースファイルのパス
# プロジェクト直下に intake.db を作成
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'intake.db')}"

# SQLAlchemy エンジンを作成
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite 用の設定
)

# セッションクラスを作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ベースクラスを作成
Base = declarative_base()


def get_db():
    """
    データベースセッションを取得するジェネレータ
    
    使用例:
        db = next(get_db())
        # DB操作
        db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    データベースとテーブルを作成する
    """
    Base.metadata.create_all(bind=engine)
