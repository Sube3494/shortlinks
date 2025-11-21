from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional


class ShortLinkCreate(BaseModel):
    """创建短链请求模型"""
    url: str
    custom_code: Optional[str] = None  # 自定义短码（可选）


class ShortLinkResponse(BaseModel):
    """短链响应模型"""
    short_code: str
    short_url: str
    original_url: str
    created_at: datetime
    click_count: int
    last_accessed: Optional[datetime] = None

    class Config:
        from_attributes = True


class ShortLinkStats(BaseModel):
    """短链统计信息模型"""
    short_code: str
    original_url: str
    click_count: int
    created_at: datetime
    last_accessed: Optional[datetime] = None

    class Config:
        from_attributes = True

