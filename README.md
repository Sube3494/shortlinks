<div align="center">
  <img src="static/shortlink.png" alt="短链服务 Logo" width="200"/>
  
  <h1>短链服务</h1>
  
  <p>基于 FastAPI 的短链服务，使用 Docker Compose 快速部署</p>
  
  <p>
    <img src="https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python&logoColor=white" alt="Python"/>
    <img src="https://img.shields.io/badge/FastAPI-0.100+-00C7B7?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
    <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"/>
    <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License"/>
  </p>
</div>

---

## 功能特性

- ✅ 创建短链（支持自定义短码）
- ✅ 短链重定向
- ✅ 访问统计（点击次数、最后访问时间）
- ✅ **URL MD5 去重**（相同 URL 自动复用已有短链，避免重复生成）
- ✅ RESTful API 接口
- ✅ 自动生成 API 文档
- ✅ CORS 支持，允许跨域调用
- ✅ 多数据库支持（SQLite / MySQL / TiDB / PostgreSQL）
- ✅ 多部署方式（Docker / Vercel Serverless）
- ✅ Web API 管理密钥（适用于 Serverless 环境）

## 部署方式

本项目支持两种部署方式：

| 方式 | 适用场景 | 数据库 | Key 管理 |
|------|---------|--------|---------|
| **Docker** | VPS / 本地开发 | SQLite (默认) / 云端数据库 (可选) | CLI 工具 / Web API |
| **Vercel** | Serverless | 云端数据库 (TiDB/MySQL) | Web API |

---

## 部署选项一: Vercel Serverless

### 优势
- ✅ 无需服务器,零运维成本
- ✅ 自动扩容,高可用性
- ✅ 全球 CDN 加速
- ✅ HTTPS 开箱即用

### 前置要求

1. **TiDB Cloud 数据库** (推荐) 或其他 MySQL 兼容数据库
   - 注册 [TiDB Cloud](https://tidbcloud.com/)
   - 创建 Serverless Tier 集群 (免费)
   - 获取连接信息 (HOST, PORT, USERNAME, PASSWORD)

2. **GitHub 仓库** (存放代码)

### 部署步骤

#### 1. 准备数据库连接字符串

TiDB 连接字符串格式:
```
mysql+pymysql://USERNAME:PASSWORD@HOST:4000/DATABASE?ssl=true
```

示例 (根据你的 TiDB 连接参数):
```
mysql+pymysql://2hVGNSjRBBnEQwq.root:YOUR_PASSWORD@gateway01.eu-central-1.prod.aws.tidbcloud.com:4000/test?ssl=true
```

> 💡 **提示**: 如果需要 SSL 证书验证,可以添加更多参数,详见 [TiDB 文档](https://docs.pingcap.com/tidbcloud/secure-connections-to-serverless-tier-clusters)

#### 2. 部署到 Vercel

**方式 A: 通过 Vercel Dashboard (推荐)**

1. Fork 本项目到你的 GitHub
2. 访问 [Vercel Dashboard](https://vercel.com/new)
3. 导入你的 GitHub 仓库
4. 配置环境变量:
   - `DATABASE_URL` = `mysql+pymysql://...` (你的 TiDB 连接字符串)
   - `BASE_URL` = `https://your-domain.vercel.app`
   - `ADMIN_KEY` = `your-super-secret-admin-key` (至少 32 字符,用于管理 API Keys)
   - `INITIAL_API_KEY` (可选) = `your-first-api-key:初始密钥` (首次部署自动创建)
5. 点击 "Deploy" 部署

**方式 B: 通过 Vercel CLI**

```bash
# 安装 Vercel CLI
npm i -g vercel

# 登录
vercel login

# 部署
vercel

# 配置环境变量
vercel env add DATABASE_URL
vercel env add BASE_URL
vercel env add ADMIN_KEY
vercel env add INITIAL_API_KEY

# 重新部署
vercel --prod
```

#### 3. 管理 API Keys (Web API)

Vercel 部署后,使用 Web API 管理 Keys:

**创建 Key:**
```bash
curl -X POST https://your-domain.vercel.app/api/admin/keys/create \
  -H "X-Admin-Key: your-super-secret-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "移动端APP", "expires_days": 90}'
```

**列出所有 Keys:**
```bash
curl https://your-domain.vercel.app/api/admin/keys/list \
  -H "X-Admin-Key: your-super-secret-admin-key"
```

**查看 Key 详情:**
```bash
curl https://your-domain.vercel.app/api/admin/keys/1 \
  -H "X-Admin-Key: your-super-secret-admin-key"
```

**更新 Key:**
```bash
curl -X PUT https://your-domain.vercel.app/api/admin/keys/1 \
  -H "X-Admin-Key: your-super-secret-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "新名称", "expires_days": 180}'
```

**撤销 Key:**
```bash
curl -X DELETE https://your-domain.vercel.app/api/admin/keys/1 \
  -H "X-Admin-Key: your-super-secret-admin-key"
```

#### 4. 验证部署

访问 `https://your-domain.vercel.app/docs` 查看 API 文档

---

## 部署选项二: Docker

### 适用场景
- VPS 服务器部署
- 本地开发测试

### 工作原理

1. **Dockerfile** 定义了如何构建镜像：
   - 基于 Python 3.11
   - 安装依赖（FastAPI、SQLAlchemy 等）
   - 复制应用代码
   - 启动 uvicorn 运行 FastAPI 应用

2. **docker-compose.yml** 定义服务：
   - `build: .` 使用当前目录的 Dockerfile 构建镜像
   - 运行 shortlink 服务，端口映射 `18000:8000`（外部18000映射到容器内8000）
   - 挂载数据库文件持久化数据

### 部署步骤

#### 1. 数据库配置 (可选)

**默认: SQLite** (无需配置,数据保存在 `./data/shortlinks.db`)

**可选: 使用云端数据库 (TiDB/MySQL)**

编辑 `docker-compose.yaml`,取消注释并配置 `DATABASE_URL`:

```yaml
environment:
  - BASE_URL=https://your-domain.com
  - DATABASE_URL=mysql+pymysql://user:pass@host:4000/db?ssl=true
```

这样 Docker 部署也可以连接云端数据库,实现数据共享。

#### 2. 配置环境变量

编辑 `docker-compose.yaml`,根据需要配置以下环境变量:

```yaml
environment:
  # ==================== 必需配置 ====================
  - BASE_URL=http://localhost:18000  # 短链服务基础 URL,生产环境改为你的域名
  
  # ==================== 管理员配置 (推荐) ====================
  - ADMIN_KEY=your-super-secret-admin-key  # 管理员密钥,用于访问 /api/admin/* 端点
  - ADMIN_PATH=/admin  # 可选,自定义管理后台路径,默认 /admin
  
  # ==================== API Key 配置 ====================
  # 方式1: 首次启动自动创建 (推荐)
  - INITIAL_API_KEY=your-first-api-key:初始密钥  # 格式: API_KEY:名称
  
  # 方式2: 传统单一密钥 (向后兼容,不推荐)
  # - API_KEY=your-api-key-here
  
  # ==================== 数据库配置 (可选) ====================
  # 默认使用 SQLite,数据保存在 ./data/shortlinks.db
  # 如需使用云端数据库,配置以下任一方式:
  
  # 方式1: 直接使用连接字符串
  # - DATABASE_URL=mysql+pymysql://user:pass@host:4000/db?ssl=true
  
  # 方式2: 使用独立变量 (TiDB Cloud 推荐)
  # - DB_HOST=gateway01.eu-central-1.prod.aws.tidbcloud.com
  # - DB_PORT=4000
  # - DB_USERNAME=your-username
  # - DB_PASSWORD=your-password
  # - DB_DATABASE=test
  
  # ==================== 站长验证 (可选) ====================
  # 微信/其他站长工具的验证文件
  # - VERIFICATION_FILENAME=09bbc06848f6945e58f841b48ee3de71.txt
  # - VERIFICATION_CONTENT=27a1dbf4cbff06d0829d3f5af88e8f2139b9f41c
```

**配置说明**:

| 变量 | 必需 | 说明 |
|------|------|------|
| `BASE_URL` | ✅ | 短链服务的基础 URL,用于生成完整短链 |
| `ADMIN_KEY` | 推荐 | 管理员密钥,用于保护管理接口 |
| `ADMIN_PATH` | 可选 | 自定义管理后台路径,默认 `/admin` |
| `INITIAL_API_KEY` | 推荐 | 首次启动自动创建的 API Key |
| `API_KEY` | 可选 | 传统单一密钥模式(向后兼容) |
| `DATABASE_URL` | 可选 | 数据库连接字符串,留空使用 SQLite |
| `DB_HOST` 等 | 可选 | TiDB/MySQL 独立配置变量 |
| `VERIFICATION_*` | 可选 | 站长验证文件配置 |

**推荐配置示例**:

```yaml
environment:
  - BASE_URL=https://short.example.com
  - ADMIN_KEY=your-super-secret-admin-key-at-least-32-chars
  - INITIAL_API_KEY=your-first-api-key:初始密钥
```

**注意**: 
- 如果数据库中没有任何 Key 且未设置 `API_KEY`,则不启用认证,任何人都可以调用 API
- 推荐使用 `ADMIN_KEY` + `INITIAL_API_KEY` 方式,通过网页后台管理多个 API Key

#### 2. 启动短链服务

```bash
# 构建镜像并启动（首次运行会自动构建）
docker-compose up -d

# 查看构建和启动日志
docker-compose up
```

访问 `http://localhost:18000` 即可使用服务。如需配置域名和 HTTPS，请自行配置反向代理（如 Nginx、Traefik 等）。

#### 3. 查看日志

```bash
# 短链服务日志
docker-compose logs -f
```

#### 4. 停止服务

```bash
docker-compose down
```


## API 使用

### API 密钥认证

**重要：** 如果设置了 `API_KEY` 环境变量，所有 API 接口都需要认证（访问短链除外）。

**认证方式：**
1. **Header 方式（推荐）：** 在请求头中添加 `X-API-Key: your-api-key`
2. **Query 参数方式：** 在URL中添加 `?api_key=your-api-key`

### 创建短链

**使用 Header 认证：**
```bash
curl -X POST 'https://xxxxxx/api/shorten' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-api-key' \
  -d '{"url": "https://www.example.com/very/long/url"}'
```

**注意：** 如果 URL 中包含特殊字符（如反斜杠 `\`），需要正确转义：
```bash
# 方法1: 使用单引号包裹 JSON，URL 中的反斜杠需要转义为 \\
curl -X POST 'https://xxxxxx/api/shorten' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-api-key' \
  -d '{"url": "https://example.com/path\\?param=value"}'

# 方法2: 使用文件（推荐，避免转义问题）
echo '{"url": "https://example.com/path?param=value"}' > /tmp/data.json
curl -X POST 'https://xxxxxxx/api/shorten' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-api-key' \
  -d @/tmp/data.json

# 方法3: 使用 Python requests（最简单）
python3 -c "
import requests
import json
response = requests.post(
    'https://xxxxxxx/api/shorten',
    headers={'X-API-Key': 'your-api-key'},
    json={'url': 'https://example.com/path?param=value'}
)
print(response.json())
"
```

**响应：**
```json
{
  "short_code": "abc123",
  "short_url": "https://xxxxxxx/abc123",
  "original_url": "https://www.example.com/very/long/url",
  "created_at": "2024-01-01T12:00:00",
  "click_count": 0,
  "last_accessed": null
}
```

### Python 调用示例

```python
import requests

API_KEY = "your-api-key"  # 替换为你的API密钥
headers = {"X-API-Key": API_KEY}

# 创建短链
response = requests.post(
    "https://xxxxxxx/api/shorten",
    json={"url": "https://www.example.com/very/long/url"},
    headers=headers
)

result = response.json()
short_url = result['short_url']  # 使用这个短链接
print(short_url)
```

**或者使用 Query 参数：**
```python
response = requests.post(
    f"https://xxxxxxxxxx/api/shorten?api_key={API_KEY}",
    json={"url": "https://www.example.com/very/long/url"}
)
```

### 使用 SDK

```python
from shortlink_client import ShortLinkClient

client = ShortLinkClient("https://xxxxxxxxx", api_key="your-api-key")
short_url = client.shorten("https://www.example.com")['short_url']
```

## API 接口

- `POST /api/shorten` - 创建短链
- `GET /{short_code}` - 访问短链（重定向）
- `GET /api/info/{short_code}` - 获取短链信息
- `GET /api/stats/{short_code}` - 获取统计信息
- `GET /api/list` - 列出所有短链
- `DELETE /api/{short_code}` - 删除短链

## API 文档

启动服务后访问：https://xxxxxxxxxx/docs

## 数据持久化

数据库文件保存在 `./data/shortlinks.db`，容器重启数据不会丢失。

## 常用命令

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 更新服务
docker-compose build
docker-compose up -d
```
