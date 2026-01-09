# Cloudflare Workers (Python) 部署参考指南 🚀

本项目采用 Cloudflare Workers (Python) + D1 数据库架构，支持通过 GitHub 自动部署。本指南供初次部署或迁移项目的技术人员参考。

## 1. 数据库准备 (Cloudflare Dashboard)

1.  登录 [Cloudflare 控制面板](https://dash.cloudflare.com/)。
2.  导航至 **存储与数据库** -> **D1**。
3.  点击 **创建数据库**，建议命名为 `shortlinks-db`。
4.  在数据库 **概述** 页面，复制并保存其 **ID (UUID)**。

## 2. API 令牌申请

由于本项目使用驱动协议与 D1 通信，需要申请一个具有库操作权限的令牌：

1.  前往 [API 令牌管理页](https://dash.cloudflare.com/profile/api-tokens)。
2.  点击 **创建令牌** -> **创建自定义令牌**。
3.  **权限配置**: 账户 — **D1** — **编辑**。
4.  **账户资源**: 包含 — 您的目标账户。
5.  生成并记录该 **Token**（仅显示一次）。

## 3. 环境变量配置 (Secrets)

在 Cloudflare Worker 的控制台 **设置 (Settings)** -> **变量 (Variables)** 中，添加以下环境变量：

| 变量名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `CLOUDFLARE_ACCOUNT_ID` | Secret | 见下方“获取 Account ID”说明 |
| `CLOUDFLARE_API_TOKEN` | Secret | 第 2 步申请的令牌 |
| `D1_DATABASE_ID` | Secret | 第 1 步记录的 UUID |
| `ADMIN_KEY` | Secret | 管理后台强密码 (建议 32 位以上) |
| `ADMIN_PATH` | Secret | 管理后台路径 (如 `/admin_portal`) |
| `IS_CLOUDFLARE` | Plain | 设置为 `true`，用于代码环境识别 |
| `BASE_URL` | Plain | (可选) 手动指定域名。留空则程序自动识别当前域名。 |

### 3.1 如何获取 Account ID
1. 登录 Cloudflare 控制台，点击左侧 **Workers 和 Pages**。
2. 在页面右下角的 **Account Details (账户详情)** 区域即可直接复制 **Account ID**。

## 4. 自动化部署

1.  在 Cloudflare **Workers 和 Pages** 页面点击 **创建应用程序**。
2.  选择 **连接到 Git**，选择本项目所在的 GitHub 仓库。
3.  配置构建信息：
    *   **框架预设**: 无 (None)。
    *   **构建命令**: 留空。
    *   **输出目录**: 留空。
4.  完成关联后，每次推送代码至仓库，Cloudflare 将自动触发构建与分发。

---

## 5. 技术说明

### 5.1 换行符说明 (LF)
本仓库已包含 `.gitattributes` 配置，确保在 Windows 环境下检出时也会保持 Linux 标准的 **LF** 换行符，以避免 Cloudflare 启动时的脚本校验错误。

### 5.2 数据库连接方式
本项目使用 `sqlalchemy-cloudflare-d1` 驱动。区别于传统的 Worker 原生绑定，该方式通过 API 模式运行，因此**必须配置 ACCOUNT_ID 和 API_TOKEN**。这种方式能完美兼容 SQLAlchemy 的各种高级查询功能。
