<div align="center">
  <img src="static/shortlink.png" alt="短链服务 Logo" width="200"/>
  
  <h1>Shortlinks</h1>
  
  <p>一个现代化的、双模架构的短链接服务，支持 <b>Cloudflare Workers</b> 和 <b>Docker</b> 部署。</p>
  
  <p>
    <img src="https://img.shields.io/badge/TypeScript-5.0+-blue?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript"/>
    <img src="https://img.shields.io/badge/Hono-Ag-E36002?style=flat-square&logo=hono&logoColor=white" alt="Hono"/>
    <img src="https://img.shields.io/badge/Cloudflare-Workers-F38020?style=flat-square&logo=cloudflare&logoColor=white" alt="Cloudflare"/>
    <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"/>
    <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License"/>
  </p>
</div>

---

## ✨ 功能特性

### 核心功能
- [x] **极简短链**：支持生成短码、自定义短码。
- [x] **智能防重**：相同 URL 自动复用已有短链，避免资源浪费。
- [x] **有效期管理**：支持设置分钟、小时、天级别的过期时间。
- [x] **访问统计**：记录点击次数、最后访问时间。
- [x] **安全认证**：API Key 机制，支持 Header/Query/Bearer 多种认证方式。

### 架构亮点
- 🚀 **双模运行时**：
    - **Cloudflare 模式**：原生 D1 数据库 + Edge 计算，全球加速，免费额度高。
    - **Node/Docker 模式**：基于 SQLite 文件数据库，数据完全掌控，适合 VPS 自建。
- 🎨 **现代化 UI**：
    - 原生 JavaScript 实现，无前端框架依赖，加载极快。
    - **移动端适配**：完美支持手机操作，自动跟随系统深色/浅色模式主题。
- � **开发友好**：
    - 自动数据库迁移 (Auto-Migration)。
    - 完整的 API 文档 (Swagger UI)。
    - 标准化的 `pnpm` 工作流。

---

## 🚀 快速开始 (Docker 部署)

最适合拥有 VPS 的用户，数据保存在本地。

### 1. 准备配置文件
复制 `docker-compose.yaml` (如有需要修改 `ADMIN_KEY`)。

```yaml
version: '3.8'
services:
  shortlink:
    image: shortlinks:latest
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data   # 数据库持久化
    environment:
      - BASE_URL=http://localhost:8000  # 你的域名
      - ADMIN_KEY=your-secret-key       # 管理密码
      - ADMIN_PATH=/admin               # 管理后台路径
```

### 2. 启动服务
```bash
docker-compose up -d
```
访问 `http://localhost:8000` 即可使用。

---

## ⚡️ 进阶部署 (Cloudflare Workers)

最适合追求高性能、零服务器运维的用户。

### 1. 准备环境
确保安装了 Node.js 和 Wrangler。
```bash
npm install -g pnpm wrangler
pnpm install
```

### 2. 配置数据库
```bash
# 1. 重要：修改配置文件
cp wrangler.toml.example wrangler.toml
# 编辑 wrangler.toml，填入你的 database_id（见下步）

# 2. 创建 D1 数据库
wrangler d1 create shortlinks-db

# 3. 初始化表结构 (第一次部署需要)
pnpm run db:migrate
```

### 3. 部署上线
```bash
# 1. 登录 Cloudflare 账号 (首次需要)
npx wrangler login

# 2. 推送代码
pnpm run deploy
```
你的服务将运行在 Cloudflare 的全球边缘节点上。

---

## 🛠 开发指南

### 本地开发 (Cloudflare 模式)
使用 Wrangler 模拟 D1 数据库。
```bash
pnpm dev
# 访问 http://localhost:8787
```

### 本地开发 (Node 模式)
使用本地 SQLite 文件，更快的开发体验。
```bash
pnpm run dev:node
# 访问 http://localhost:8000
```

---

## 📝 API 文档

系统内置了美观的 API 文档页面。
启动服务后，访问 `/docs` (例如 `http://localhost:8000/docs`) 即可查看所有接口定义和在线调试。

### 常用接口示例

**创建短链**
```bash
curl -X POST http://localhost:8000/api/shorten \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.example.com", "custom_code": "my-link"}'
```

**获取统计**
```bash
curl http://localhost:8000/api/info/my-link \
  -H "X-API-Key: your-api-key"
```

---

## 🤝 贡献 & 反馈

- 遇到问题请提交 Issue。
- 欢迎 PR 改进代码。

License: MIT
