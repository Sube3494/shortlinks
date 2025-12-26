from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

# 数据库配置
# 优先级: 1. DATABASE_URL -> 2. TiDB/MySQL 环境变量 -> 3. SQLite (默认)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # 检查是否配置了 TiDB/MySQL 独立环境变量
    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USERNAME")
    db_pass = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_DATABASE", "test")
    db_port = os.getenv("DB_PORT", "4000")
    
    if db_host and db_user and db_pass:
        # 自动构建 MySQL 连接字符串 (适配 TiDB)
        # 注意: TiDB Serverless 强制要求 SSL，pymysql 默认 ssl=True 即可，或显式指定
        DATABASE_URL = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?ssl_verify_cert=true&ssl_verify_identity=true"
        print(f"✅ 检测到 TiDB/MySQL 环境变量，已自动配置连接: {db_host}")
    else:
        # 默认使用 SQLite (Docker/本地开发)
        db_path = os.getenv("DATABASE_PATH", "/app/data/shortlinks.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        DATABASE_URL = f"sqlite:///{db_path}"

# 根据数据库类型配置引擎参数
if DATABASE_URL.startswith("sqlite"):
    # SQLite 需要 check_same_thread=False
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    # MySQL/PostgreSQL 配置连接池
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # 连接前验证可用性
        pool_recycle=3600,   # 每小时回收连接
        pool_size=5,         # Serverless 环境保持小连接池
        max_overflow=10
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ShortLink(Base):
    """短链数据模型"""
    __tablename__ = "shortlinks"

    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String(10), unique=True, index=True, nullable=False)
    original_url = Column(Text, nullable=False)
    url_hash = Column(String(32), index=True, nullable=True)  # URL MD5 哈希，用于去重
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

