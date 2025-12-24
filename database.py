from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

# 数据库文件路径
import os
db_path = os.getenv("DATABASE_PATH", "/app/data/shortlinks.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ShortLink(Base):
    """短链数据模型"""
    __tablename__ = "shortlinks"

    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String(10), unique=True, index=True, nullable=False)
    original_url = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    click_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # 过期时间
    
    # 外键: 关联到创建者 API Key
    created_by_key_id = Column(Integer, ForeignKey('api_keys.id'), nullable=True, index=True)
    
    # 关系: 反向引用到 APIKey
    created_by = relationship("APIKey", back_populates="shortlinks")


class APIKey(Base):
    """API密钥数据模型"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)  # Key 名称/备注
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=True)  # 过期时间
    last_used_at = Column(DateTime, nullable=True)  # 最后使用时间
    usage_count = Column(Integer, default=0)  # 使用次数
    is_active = Column(Boolean, default=True)  # 是否启用
    
    # 关系: 一个 Key 可以创建多个短链
    shortlinks = relationship("ShortLink", back_populates="created_by")


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

