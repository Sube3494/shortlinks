# Cloudflare Workers 部署指南 🚀

本项目支持部署到 Cloudflare Workers，使用 D1 作为数据库。本指南基于实际代码配置编写。

## 📌 核心要点

根据 `database.py` 的实际实现，本项目通过 **环境变量** 连接 D1 数据库（使用 `sqlalchemy-cloudflare-d1` 驱动），**不需要**在 `wrangler.toml` 中配置 D1 绑定。

## 🚀 部署步骤

### 第 1 步: 创建 D1 数据库

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 导航至 **Workers & Pages** → **D1**
3. 点击 **创建数据库**，命名如 `shortlinks-db`
4. 记录数据库 ID（格式：`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`）

### 第 2 步: 创建 API Token

1. 前往 [API Tokens 页面](https://dash.cloudflare.com/profile/api-tokens)
2. 点击 **创建令牌** → **创建自定义令牌**
3. 配置权限：
   - **账户** - **D1** - **编辑**
4. 账户资源：选择你的账户
5. 创建并 **复制 Token**（仅显示一次！）

### 第 3 步: 获取 Account ID

1. 在 Dashboard 左侧点击 **Workers & Pages**
2. 右下角 **Account Details** 区域查看并复制 **Account ID**

### 第 4 步: 配置环境变量

在 Worker 的 **设置 (Settings)** → **变量 (Variables)** 中添加：

#### 必需的 Secret 变量

| 变量名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `CLOUDFLARE_ACCOUNT_ID` | Secret | Cloudflare Account ID | `abc123...` |
| `CLOUDFLARE_API_TOKEN` | Secret | API Token (需 D1 编辑权限) | `xyz789...` |
| `D1_DATABASE_ID` | Secret | D1 数据库 ID | `xxxxxxxx-xxxx-...` |
| `ADMIN_KEY` | Secret | 管理后台密钥 | 至少 32 位随机字符串 |
| `ADMIN_PATH` | Secret | 管理后台路径 | `/admin` 或 `/my-secret-path` |

#### 可选的环境变量

| 变量名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `BASE_URL` | Plain | (自动识别) | 手动指定域名，如 `https://s.example.com` |
| `IS_CLOUDFLARE` | Plain | `true` | `wrangler.toml` 已配置，无需手动添加 |

> [!NOTE]
> `wrangler.toml` 中已设置 `IS_CLOUDFLARE = "true"`，会自动禁用 APScheduler 定时任务（Workers 环境不支持）

### 第 5 步: 初始化数据库表

使用 Wrangler CLI 在 D1 中创建表结构：

```bash
npx wrangler d1 execute shortlinks-db --remote --command="
CREATE TABLE IF NOT EXISTS shortlinks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code TEXT UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    url_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    click_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    expires_at TIMESTAMP,
    created_by_key_id INTEGER
);

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_shortlinks_short_code ON shortlinks(short_code);
CREATE INDEX idx_shortlinks_url_hash ON shortlinks(url_hash);
CREATE INDEX idx_shortlinks_created_by ON shortlinks(created_by_key_id);
CREATE INDEX idx_api_keys_key ON api_keys(key);
CREATE INDEX idx_system_config_key ON system_config(key);
"
```

> 也可在 D1 控制台的 **Console** 标签中执行上述 SQL 语句

### 第 6 步: 部署 Worker

#### 方式 A: 通过 GitHub 自动部署（推荐）

> [!IMPORTANT]
> **必须选择 Workers，不是 Pages！** 如果看到 `.pages.dev` 域名说明选错了。

1. 在 Cloudflare Dashboard 点击 **创建应用程序**
2. **选择 Workers 标签页**（不是 Pages！）
3. 点击 **连接到 Git**，选择仓库
4. **构建配置**：
   - 构建命令：**留空**
   - 输出目录：**留空**
5. 关联后，每次推送代码会自动部署

#### 方式 B: 通过 Wrangler CLI 部署

```bash
# 登录
npx wrangler login

# 部署
npx wrangler deploy
```

### 第 7 步: 创建首个 API Key

部署后，使用 `ADMIN_KEY` 创建第一个 API Key：

```bash
curl -X POST https://your-worker.workers.dev/api/admin/keys/create \
  -H "X-Admin-Key: 你的ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "默认密钥", "expires_days": 365}'
```

### 第 8 步: 验证部署

访问你的 Worker 域名：
- `https://shortlinks.your-account.workers.dev/` - 前端界面
- `https://shortlinks.your-account.workers.dev/docs` - API 文档

---

## ⚠️ 常见问题

### Q1: 为什么不用 `wrangler.toml` 的 D1 绑定？

**A:** 本项目使用 `sqlalchemy-cloudflare-d1` 驱动，通过 REST API 访问 D1，与 Workers 原生绑定不同：

- **原生绑定**：适合直接使用 Worker API（如 `env.DB.prepare()`）
- **SQLAlchemy 驱动**：支持完整 ORM 功能，代码可在 Docker/Vercel/Workers 多环境运行

数据库连接逻辑见 `database.py` 第 12-18 行。

### Q2: `BASE_URL` 必须配置吗？

**不必须**。代码会自动识别请求域名（`main.py` 第 89-99 行）：

```python
def resolve_base_url(request: Request) -> str:
    if BASE_URL_ENV:
        return BASE_URL_ENV
    return f"{request.url.scheme}://{request.url.netloc}"
```

仅在使用自定义域名且自动识别不准确时才需手动配置。

### Q3: 如何访问管理后台？

访问 `https://your-worker.workers.dev{ADMIN_PATH}`（如 `/admin`），需提供 `ADMIN_KEY` 认证。

---

## 📋 配置检查清单

部署前确认：

- [ ] 已创建 D1 数据库并记录 ID
- [ ] 已创建 API Token（权限：D1 编辑）
- [ ] 已获取 Account ID
- [ ] 已配置 5 个必需的环境变量
- [ ] 已初始化数据库表结构
- [ ] 已创建第一个 API Key
- [ ] （可选）已配置自定义域名

## 🔗 相关文件

- `database.py` (第 12-18 行) - D1 连接配置逻辑
- `wrangler.toml` - Worker 基础配置
- `.env.example` (第 15-19 行) - 环境变量示例
- `main.py` (第 89-99 行) - BASE_URL 动态识别逻辑
