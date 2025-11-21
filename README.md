# 短链服务

基于 FastAPI 的短链服务，使用 Docker Compose + Caddy 部署，自动配置 HTTPS。

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

3. **Caddyfile** 配置外部 Caddy：
   - 反向代理到 `localhost:18000`
   - 自动申请 SSL 证书

### 部署步骤

#### 1. 配置 DNS

将域名 `shortlinks.sube.top` 的 A 记录指向服务器 IP。

#### 2. 配置 API 密钥（可选）

编辑 `docker-compose.yml`，设置 `API_KEY` 环境变量：

```yaml
environment:
  - BASE_URL=https://shortlinks.sube.top
  - API_KEY=your-secret-api-key-here  # 设置你的API密钥
```

**注意：** 如果不设置 `API_KEY` 或设置为空，则不启用认证，任何人都可以调用API。

#### 3. 启动短链服务

```bash
# 构建镜像并启动（首次运行会自动构建）
docker-compose up -d

# 查看构建和启动日志
docker-compose up
```

#### 4. 配置外部 Caddy

将 `Caddyfile` 复制到 Caddy 配置目录，或使用当前目录的 Caddyfile：

```bash
# 如果 Caddy 使用系统服务
sudo cp Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy

# 或者直接运行 Caddy
caddy run --config Caddyfile
```

Caddy 会自动申请 Let's Encrypt SSL 证书并配置 HTTPS。

#### 5. 查看日志

```bash
# 短链服务日志
docker-compose logs -f

# Caddy 日志（如果使用系统服务）
sudo journalctl -u caddy -f
```

#### 6. 停止服务

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
curl -X POST 'https://shortlinks.sube.top/api/shorten' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-api-key' \
  -d '{"url": "https://www.example.com/very/long/url"}'
```

**注意：** 如果 URL 中包含特殊字符（如反斜杠 `\`），需要正确转义：
```bash
# 方法1: 使用单引号包裹 JSON，URL 中的反斜杠需要转义为 \\
curl -X POST 'https://shortlinks.sube.top/api/shorten' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-api-key' \
  -d '{"url": "https://example.com/path\\?param=value"}'

# 方法2: 使用文件（推荐，避免转义问题）
echo '{"url": "https://example.com/path?param=value"}' > /tmp/data.json
curl -X POST 'https://shortlinks.sube.top/api/shorten' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-api-key' \
  -d @/tmp/data.json

# 方法3: 使用 Python requests（最简单）
python3 -c "
import requests
import json
response = requests.post(
    'https://shortlinks.sube.top/api/shorten',
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
  "short_url": "https://shortlinks.sube.top/abc123",
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
    "https://shortlinks.sube.top/api/shorten",
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
    f"https://shortlinks.sube.top/api/shorten?api_key={API_KEY}",
    json={"url": "https://www.example.com/very/long/url"}
)
```

### 使用 SDK

```python
from shortlink_client import ShortLinkClient

client = ShortLinkClient("https://shortlinks.sube.top", api_key="your-api-key")
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

启动服务后访问：https://shortlinks.sube.top/docs

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
