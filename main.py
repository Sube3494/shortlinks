from fastapi import FastAPI, HTTPException, Depends, Request, Header, Query, Request
from fastapi.responses import RedirectResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import os
import json
import re

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # 如果没有安装 python-dotenv，跳过

from database import get_db, init_db, ShortLink
from models import ShortLinkCreate, ShortLinkResponse, ShortLinkStats, BatchShortLinkCreate
from utils import get_unique_short_code, normalize_url, validate_url

# 初始化数据库
init_db()

app = FastAPI(
    title="短链服务 API",
    description="一个简单易用的短链服务，支持API调用",
    version="1.0.0"
)

# 修复 JSON 中无效转义字符的中间件
class FixJsonEscapeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        if request.url.path == "/api/shorten" and request.method == "POST":
            body = await request.body()
            if body:
                body_str = body.decode('utf-8')
                # 修复无效的转义序列：\? \= \& 等（保留有效的转义序列）
                fixed_body = re.sub(r'\\([^"\\/bfnrtu0-9])', r'\1', body_str)
                # 重新创建请求对象
                async def receive():
                    return {"type": "http.request", "body": fixed_body.encode('utf-8')}
                request._receive = receive
        
        response = await call_next(request)
        return response

app.add_middleware(FixJsonEscapeMiddleware)

# 配置CORS，允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass  # 如果 static 目录不存在，跳过

# 获取基础URL（用于生成完整短链）
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# API密钥（从环境变量读取）
API_KEY = os.getenv("API_KEY", "")

# API密钥Header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    api_key: Optional[str] = Query(None)
):
    """
    验证API密钥
    支持通过 Header (X-API-Key) 或 Query参数 (api_key) 传递
    """
    # 如果没有设置API_KEY，则不启用认证
    if not API_KEY:
        return True
    
    # 优先使用Header中的密钥，如果没有则使用Query参数
    provided_key = x_api_key or api_key
    
    # 如果设置了API_KEY但没有提供密钥，拒绝访问
    if not provided_key:
        raise HTTPException(
            status_code=401,
            detail="缺少API密钥，请在Header中添加 X-API-Key 或在URL中添加 api_key 参数"
        )
    
    # 验证密钥
    if provided_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="无效的API密钥"
        )
    
    return True


@app.get("/")
async def root():
    """API根路径，返回网页界面或API信息"""
    # 如果存在静态文件，返回网页
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    
    # 否则返回API信息
    return {
        "message": "短链服务 API",
        "version": "1.0.0",
        "docs": "/docs",
        "web": "/static/index.html",
        "endpoints": {
            "创建短链": "POST /api/shorten",
            "获取短链信息": "GET /api/info/{short_code}",
            "获取短链统计": "GET /api/stats/{short_code}",
            "列出所有短链": "GET /api/list",
            "删除短链": "DELETE /api/{short_code}",
            "访问短链": "GET /{short_code}"
        }
    }


@app.post("/api/shorten", response_model=ShortLinkResponse)
async def create_short_link(
    request: ShortLinkCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key)
):
    """
    创建短链
    
    - **url**: 原始URL（必需）
    - **custom_code**: 自定义短码（可选，6-10个字符）
    """
    # 规范化URL（会自动清理无效转义字符）
    original_url = normalize_url(request.url)
    
    # 验证URL格式
    if not validate_url(original_url):
        raise HTTPException(status_code=400, detail="无效的URL格式")
    
    # 处理自定义短码或生成新短码
    if request.custom_code:
        # 验证自定义短码格式
        if not (6 <= len(request.custom_code) <= 10):
            raise HTTPException(
                status_code=400,
                detail="自定义短码长度必须在6-10个字符之间"
            )
        if not request.custom_code.isalnum():
            raise HTTPException(
                status_code=400,
                detail="自定义短码只能包含字母和数字"
            )
        
        # 检查自定义短码是否已存在
        existing = db.query(ShortLink).filter(
            ShortLink.short_code == request.custom_code
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"短码 '{request.custom_code}' 已被使用"
            )
        short_code = request.custom_code
    else:
        short_code = get_unique_short_code()
    
    # 计算过期时间
    expires_at = None
    if request.expires_in_hours and request.expires_in_hours > 0:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(hours=request.expires_in_hours)
    
    # 创建短链记录
    short_link = ShortLink(
        short_code=short_code,
        original_url=original_url,
        expires_at=expires_at
    )
    
    db.add(short_link)
    db.commit()
    db.refresh(short_link)
    
    return ShortLinkResponse(
        short_code=short_link.short_code,
        short_url=f"{BASE_URL}/{short_link.short_code}",
        original_url=short_link.original_url,
        created_at=short_link.created_at,
        click_count=short_link.click_count,
        last_accessed=short_link.last_accessed,
        expires_at=short_link.expires_at
    )


@app.post("/api/shorten/batch", response_model=List[ShortLinkResponse])
async def create_batch_short_links(
    request: BatchShortLinkCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key)
):
    """
    批量创建短链
    
    - **urls**: URL列表（必需）
    - **expires_in_hours**: 过期时间（小时数，可选，应用于所有URL）
    """
    results = []
    errors = []
    
    for idx, url in enumerate(request.urls):
        try:
            # 规范化URL
            original_url = normalize_url(url.strip())
            
            # 验证URL格式
            if not validate_url(original_url):
                errors.append(f"第 {idx + 1} 个URL无效: {url}")
                continue
            
            # 生成短码
            short_code = get_unique_short_code()
            
            # 计算过期时间
            expires_at = None
            if request.expires_in_hours and request.expires_in_hours > 0:
                from datetime import timedelta
                expires_at = datetime.utcnow() + timedelta(hours=request.expires_in_hours)
            
            # 创建短链记录
            short_link = ShortLink(
                short_code=short_code,
                original_url=original_url,
                expires_at=expires_at
            )
            
            db.add(short_link)
            db.commit()
            db.refresh(short_link)
            
            results.append(ShortLinkResponse(
                short_code=short_link.short_code,
                short_url=f"{BASE_URL}/{short_link.short_code}",
                original_url=short_link.original_url,
                created_at=short_link.created_at,
                click_count=short_link.click_count,
                last_accessed=short_link.last_accessed,
                expires_at=short_link.expires_at
            ))
        except Exception as e:
            errors.append(f"第 {idx + 1} 个URL处理失败: {str(e)}")
            db.rollback()
            continue
    
    if errors and not results:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    
    return results


@app.get("/{short_code}")
async def redirect_to_url(short_code: str, db: Session = Depends(get_db)):
    """
    重定向到原始URL
    """
    short_link = db.query(ShortLink).filter(
        ShortLink.short_code == short_code
    ).first()
    
    if not short_link:
        raise HTTPException(status_code=404, detail="短链不存在")
    
    # 检查是否过期
    if short_link.expires_at and datetime.utcnow() > short_link.expires_at:
        raise HTTPException(status_code=410, detail="短链已过期")
    
    # 更新访问统计
    short_link.click_count += 1
    short_link.last_accessed = datetime.utcnow()
    db.commit()
    
    return RedirectResponse(url=short_link.original_url, status_code=302)


@app.get("/api/info/{short_code}", response_model=ShortLinkResponse)
async def get_short_link_info(
    short_code: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key)
):
    """
    获取短链详细信息
    """
    short_link = db.query(ShortLink).filter(
        ShortLink.short_code == short_code
    ).first()
    
    if not short_link:
        raise HTTPException(status_code=404, detail="短链不存在")
    
    return ShortLinkResponse(
        short_code=short_link.short_code,
        short_url=f"{BASE_URL}/{short_link.short_code}",
        original_url=short_link.original_url,
        created_at=short_link.created_at,
        click_count=short_link.click_count,
        last_accessed=short_link.last_accessed,
        expires_at=short_link.expires_at
    )


@app.get("/api/stats/{short_code}", response_model=ShortLinkStats)
async def get_short_link_stats(
    short_code: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key)
):
    """
    获取短链统计信息
    """
    short_link = db.query(ShortLink).filter(
        ShortLink.short_code == short_code
    ).first()
    
    if not short_link:
        raise HTTPException(status_code=404, detail="短链不存在")
    
    return ShortLinkStats(
        short_code=short_link.short_code,
        original_url=short_link.original_url,
        click_count=short_link.click_count,
        created_at=short_link.created_at,
        last_accessed=short_link.last_accessed
    )


@app.get("/api/list", response_model=List[ShortLinkResponse])
async def list_short_links(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key)
):
    """
    列出所有短链
    
    - **skip**: 跳过的记录数（分页）
    - **limit**: 返回的最大记录数
    """
    short_links = db.query(ShortLink).offset(skip).limit(limit).all()
    
    return [
        ShortLinkResponse(
            short_code=link.short_code,
            short_url=f"{BASE_URL}/{link.short_code}",
            original_url=link.original_url,
            created_at=link.created_at,
            click_count=link.click_count,
            last_accessed=link.last_accessed,
            expires_at=link.expires_at
        )
        for link in short_links
    ]


@app.delete("/api/{short_code}")
async def delete_short_link(
    short_code: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key)
):
    """
    删除短链
    """
    short_link = db.query(ShortLink).filter(
        ShortLink.short_code == short_code
    ).first()
    
    if not short_link:
        raise HTTPException(status_code=404, detail="短链不存在")
    
    db.delete(short_link)
    db.commit()
    
    return {"message": f"短链 '{short_code}' 已成功删除"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

