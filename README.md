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
- ✅ RESTful API 接口
- ✅ 自动生成 API 文档
- ✅ CORS 支持，允许跨域调用

## 部署

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

#### 1. 配置 API 密钥

**推荐方式：使用多 Key 管理（新功能）**

服务启动后，使用命令行工具管理 API Keys：

```bash
# 创建第一个 Key
docker exec -it shortlink-app python manage_keys.py create --name "主密钥"

# 创建带过期时间的 Key
docker exec -it shortlink-app python manage_keys.py create --name "临时密钥" --expires-days 30

# 查看所有 Key
docker exec -it shortlink-app python manage_keys.py list
```

**传统方式：使用环境变量（向后兼容）**

编辑 `docker-compose.yml`，设置 `API_KEY` 环境变量：

```yaml
environment:
  - BASE_URL=https://XXXX
  - API_KEY=your-secret-api-key-here  # 设置你的API密钥
```

**注意：** 
- 如果数据库中没有任何 Key 且未设置环境变量，则不启用认证，任何人都可以调用API
- 多 Key 管理优先于环境变量，推荐使用多 Key 方式

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

## API Key 管理

### 命令行工具

服务支持多 API Key 管理,每个 Key 可以独立设置名称、过期时间并追踪使用统计。

#### 创建 API Key

```bash
# 创建永久有效的 Key
docker exec -it shortlink-app python manage_keys.py create --name "移动端APP"

# 创建带过期时间的 Key (90天后过期)
docker exec -it shortlink-app python manage_keys.py create --name "临时密钥" --expires-days 90
```

**输出示例：**
```
✅ API Key 创建成功!

ID: 1
名称: 移动端APP
密钥: AbCdEf123456...xyz  (请妥善保存,仅显示一次!)
创建时间: 2025-12-24 15:30:00
过期时间: 永不过期
```

#### 列出所有 Key

```bash
docker exec -it shortlink-app python manage_keys.py list
```

**输出示例：**
```
🔑 共有 2 个活跃的 API Keys:

ID    名称                密钥前缀         过期时间         最后使用              使用次数    
---------------------------------------------------------------------------------------------
1     移动端APP           AbCdEf123...    Never           2小时前               234         
2     CI/CD流水线         XyZ789Abc...    2025-03-20      5分钟前               45          
```

#### 查看 Key 详情

```bash
docker exec -it shortlink-app python manage_keys.py info 1
```

#### 更新 Key

```bash
# 修改名称
docker exec -it shortlink-app python manage_keys.py update 1 --name "移动端APP-v2"

# 延长有效期
docker exec -it shortlink-app python manage_keys.py update 1 --expires-days 180

# 设置为永不过期
docker exec -it shortlink-app python manage_keys.py update 1 --expires-days 0
```

#### 撤销 Key

```bash
# 软删除,Key 立即失效但保留记录
docker exec -it shortlink-app python manage_keys.py revoke 1
```

#### 删除 Key

```bash
# 永久删除,需要 --confirm 确认
docker exec -it shortlink-app python manage_keys.py delete 1 --confirm
```

### 向后兼容说明

- **优先级**: 数据库中的 Key > 环境变量 `API_KEY`
- **建议**: 新项目使用多 Key 管理,旧项目可继续使用环境变量
- **迁移**: 可同时保留环境变量作为紧急后备密钥

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
