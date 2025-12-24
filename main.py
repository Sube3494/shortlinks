from fastapi import FastAPI, HTTPException, Depends, Header, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
import os
import json
import re
import random
import string
from urllib.parse import unquote, quote
import unicodedata
from collections import defaultdict
import time

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # 如果没有安装 python-dotenv，跳过

from database import get_db, init_db, ShortLink, APIKey
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
static_dirs = ["static", os.path.join(os.path.dirname(__file__), "static"), "/app/static"]
for static_dir in static_dirs:
    if os.path.exists(static_dir):
        try:
            app.mount("/static", StaticFiles(directory=static_dir), name="static")
            break
        except Exception:
            continue

# 获取基础URL（用于生成完整短链）
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# API密钥Header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# ==================== IP 限流配置 ====================
# 防暴力破解配置
MAX_FAILURES = 5           # 最大失败次数
FAILURE_WINDOW = 300       # 失败窗口期（秒）= 5分钟
BAN_DURATION = 900         # 封禁时长（秒）= 15分钟

# IP 限流数据结构
# {ip: [(timestamp1, timestamp2, ...), ban_until]}
ip_failures = defaultdict(lambda: {'attempts': [], 'ban_until': None})

def get_client_ip(request: Request) -> str:
    """获取客户端真实 IP"""
    # 优先从 X-Forwarded-For 获取（如果有反向代理）
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    
    # 其次从 X-Real-IP 获取
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    
    # 最后使用直连 IP
    return request.client.host if request.client else 'unknown'

def is_ip_banned(ip: str) -> bool:
    """检查 IP 是否被封禁"""
    if ip not in ip_failures:
        return False
    
    ban_until = ip_failures[ip]['ban_until']
    if ban_until and time.time() < ban_until:
        return True
    
    # 解除过期的封禁
    if ban_until and time.time() >= ban_until:
        ip_failures[ip]['ban_until'] = None
        ip_failures[ip]['attempts'] = []
    
    return False

def record_auth_failure(ip: str):
    """记录认证失败"""
    now = time.time()
    
    # 清理过期的失败记录
    ip_failures[ip]['attempts'] = [
        t for t in ip_failures[ip]['attempts']
        if now - t < FAILURE_WINDOW
    ]
    
    # 添加当前失败记录
    ip_failures[ip]['attempts'].append(now)
    
    # 检查是否达到封禁阈值
    if len(ip_failures[ip]['attempts']) >= MAX_FAILURES:
        ip_failures[ip]['ban_until'] = now + BAN_DURATION
        print(f"⚠️  IP {ip} 被临时封禁 {BAN_DURATION//60} 分钟（失败尝试: {len(ip_failures[ip]['attempts'])}）")
        return True
    
    return False

def get_remaining_ban_time(ip: str) -> int:
    """获取剩余封禁时间（秒）"""
    if ip not in ip_failures:
        return 0
    
    ban_until = ip_failures[ip]['ban_until']
    if not ban_until:
        return 0
    
    remaining = int(ban_until - time.time())
    return max(0, remaining)


def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    api_key: Optional[str] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db)
) -> Optional[int]:
    """
    验证API密钥并返回 Key ID
    支持通过 Header (X-API-Key) 或 Query参数 (api_key) 传递
    集成 IP 限流防暴力破解
    返回: Key ID (如果认证成功) 或 None (如果无需认证)
    """
    # 获取客户端 IP
    client_ip = get_client_ip(request)
    
    # 检查 IP 是否被封禁
    if is_ip_banned(client_ip):
        remaining = get_remaining_ban_time(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"访问受限，请在 {remaining//60} 分钟后重试"
        )
    
    # 获取提供的密钥
    provided_key = x_api_key or api_key
    
    # 1. 如果提供了密钥，查询数据库
    if provided_key:
        db_key = db.query(APIKey).filter(
            APIKey.key == provided_key,
            APIKey.is_active == True
        ).first()
        
        if db_key:
            # 检查是否过期
            if db_key.expires_at and datetime.now() > db_key.expires_at:
                # 记录失败
                record_auth_failure(client_ip)
                raise HTTPException(
                    status_code=403,
                    detail="API Key 已过期"
                )
            
            # 更新使用统计
            db_key.last_used_at = datetime.now()
            db_key.usage_count += 1
            db.commit()
            
            return db_key.id  # 返回 Key ID
        else:
            # 提供了密钥但无效 - 记录失败
            record_auth_failure(client_ip)
            raise HTTPException(
                status_code=403,
                detail="无效的API密钥"
            )
    
    # 2. 没有提供密钥，检查是否需要认证
    has_db_keys = db.query(APIKey).filter(APIKey.is_active == True).count() > 0
    
    if has_db_keys:
        # 有配置认证但没有提供密钥
        raise HTTPException(
            status_code=401,
            detail="缺少API密钥，请在Header中添加 X-API-Key 或在URL中添加 api_key 参数"
        )
    
    # 3. 无任何认证要求，允许访问
    return None


@app.get("/")
async def root(request: Request):
    """API根路径，返回网页界面或API信息"""
    # 获取当前工作目录和可能的静态文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(current_dir, "static", "index.html"),
        os.path.join(os.getcwd(), "static", "index.html"),
        "static/index.html",
        "/app/static/index.html",
    ]
    
    # 尝试找到并返回网页文件
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path) and os.path.isfile(abs_path):
            return FileResponse(abs_path)
    
    # 如果找不到文件，返回重定向到静态文件路由或API信息
    # 尝试通过静态文件路由访问
    return RedirectResponse(url="/static/index.html")


@app.get("/api/key/info")
async def get_current_key_info(
    key_id: Optional[int] = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    获取当前 API Key 的信息
    """
    if key_id is None:
        # 无认证模式
        return {
            "authenticated": False,
            "message": "服务未启用认证"
        }
    
    # 查询当前 Key
    api_key = db.query(APIKey).filter(APIKey.id == key_id).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="Key 不存在")
    
    return {
        "authenticated": True,
        "name": api_key.name,
        "created_at": api_key.created_at.isoformat(),
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        "is_expired": api_key.expires_at and datetime.now() > api_key.expires_at if api_key.expires_at else False,
        "usage_count": api_key.usage_count,
        "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None
    }


@app.post("/api/shorten", response_model=ShortLinkResponse)
async def create_short_link(
    request: ShortLinkCreate,
    db: Session = Depends(get_db),
    key_id: Optional[int] = Depends(verify_api_key)  # 获取当前 Key ID
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
        expires_at = datetime.now() + timedelta(hours=request.expires_in_hours)
    
    # 创建短链记录
    short_link = ShortLink(
        short_code=short_code,
        original_url=original_url,
        expires_at=expires_at,
        created_by_key_id=key_id  # 记录创建者
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
    key_id: Optional[int] = Depends(verify_api_key)  # 获取当前 Key ID
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
                expires_at = datetime.now() + timedelta(hours=request.expires_in_hours)
            
            # 创建短链记录
            short_link = ShortLink(
                short_code=short_code,
                original_url=original_url,
                expires_at=expires_at,
                created_by_key_id=key_id  # 记录创建者
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
    if short_link.expires_at and datetime.now() > short_link.expires_at:
        raise HTTPException(status_code=410, detail="短链已过期")
    
    # 更新访问统计
    short_link.click_count += 1
    short_link.last_accessed = datetime.now()
    db.commit()
    
    return RedirectResponse(url=short_link.original_url, status_code=302)


@app.get("/api/info/{short_code}", response_model=ShortLinkResponse)
async def get_short_link_info(
    short_code: str,
    db: Session = Depends(get_db),
    key_id: Optional[int] = Depends(verify_api_key)  # 获取当前 Key ID
):
    """
    获取短链详细信息
    只能查询自己创建的短链
    """
    short_link = db.query(ShortLink).filter(
        ShortLink.short_code == short_code
    ).first()
    
    if not short_link:
        raise HTTPException(status_code=404, detail="短链不存在")
    
    # 权限检查: 只能查询自己创建的
    if key_id is not None and short_link.created_by_key_id != key_id:
        raise HTTPException(status_code=403, detail="无权查看此短链")
    
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
    key_id: Optional[int] = Depends(verify_api_key)  # 获取当前 Key ID
):
    """
    获取短链统计信息
    只能查询自己创建的短链
    """
    short_link = db.query(ShortLink).filter(
        ShortLink.short_code == short_code
    ).first()
    
    if not short_link:
        raise HTTPException(status_code=404, detail="短链不存在")
    
    # 权限检查: 只能查询自己创建的
    if key_id is not None and short_link.created_by_key_id != key_id:
        raise HTTPException(status_code=403, detail="无权查看此短链")
    
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
    key_id: Optional[int] = Depends(verify_api_key)  # 获取当前 Key ID
):
    """
    列出短链
    只返回当前 Key 创建的短链
    
    - **skip**: 跳过的记录数（分页）
    - **limit**: 返回的最大记录数
    """
    # 查询短链，添加权限过滤
    query = db.query(ShortLink)
    
    # 如果有认证，只显示当前 Key 创建的
    if key_id is not None:
        query = query.filter(ShortLink.created_by_key_id == key_id)
    # 否则显示所有（开放模式）
    
    short_links = query.offset(skip).limit(limit).all()
    
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
    key_id: Optional[int] = Depends(verify_api_key)  # 获取当前 Key ID
):
    """
    删除短链
    只能删除自己创建的短链
    """
    short_link = db.query(ShortLink).filter(
        ShortLink.short_code == short_code
    ).first()
    
    if not short_link:
        raise HTTPException(status_code=404, detail="短链不存在")
    
    # 权限检查: 只能删除自己创建的
    if key_id is not None and short_link.created_by_key_id != key_id:
        raise HTTPException(status_code=403, detail="无权删除此短链")
    
    db.delete(short_link)
    db.commit()
    
    return {"message": f"短链 '{short_code}' 已成功删除"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

