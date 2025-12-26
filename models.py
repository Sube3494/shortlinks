from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional, List


class ShortLinkCreate(BaseModel):
    """创建短链请求模型"""
    url: str
    custom_code: Optional[str] = None  # 自定义短码（可选）
    expires_in_hours: Optional[int] = None  # 过期时间（小时数，可选）
    expires_in_minutes: Optional[int] = None  # 过期时间（分钟数，可选，优先级高于 hours）


class BatchShortLinkCreate(BaseModel):
    """批量创建短链请求模型"""
    urls: List[str]  # URL列表
    expires_in_hours: Optional[int] = None  # 过期时间（小时数，可选，应用于所有URL）
    expires_in_minutes: Optional[int] = None  # 过期时间（分钟数，可选，优先级高于 hours）


class ShortLinkResponse(BaseModel):
    """短链响应模型"""
    short_code: str
    short_url: str
    original_url: str
    created_at: datetime
    click_count: int
    last_accessed: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # 过期时间

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


class APIKeyCreate(BaseModel):
    """创建API密钥请求模型"""
    name: str
    expires_in_days: Optional[int] = None  # 过期天数，可选


class APIKeyResponse(BaseModel):
    """API密钥响应模型"""
    id: int
    key: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    usage_count: int
    is_active: bool

    class Config:
        from_attributes = True


class APIKeyUpdate(BaseModel):
    """更新API密钥请求模型"""
    name: Optional[str] = None
    expires_in_days: Optional[int] = None
    is_active: Optional[bool] = None

