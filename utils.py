import string
import random
from database import SessionLocal, ShortLink


def generate_short_code(length: int = 6) -> str:
    """生成随机短码"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def get_unique_short_code(length: int = 6) -> str:
    """获取唯一的短码"""
    db = SessionLocal()
    try:
        while True:
            code = generate_short_code(length)
            existing = db.query(ShortLink).filter(ShortLink.short_code == code).first()
            if not existing:
                return code
    finally:
        db.close()


def validate_url(url: str) -> bool:
    """验证URL格式"""
    return url.startswith(('http://', 'https://'))


def normalize_url(url: str) -> str:
    """规范化URL（确保有协议前缀，清理无效转义字符）"""
    # 清理URL中常见的无效转义字符（这些可能是JSON转义错误导致的）
    cleaned_url = url.replace('\\?', '?').replace('\\=', '=').replace('\\&', '&')
    
    if not cleaned_url.startswith(('http://', 'https://')):
        return 'https://' + cleaned_url
    return cleaned_url

