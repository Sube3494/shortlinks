import 'dotenv/config';
import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { createClient } from '@libsql/client';
import { app } from './index';

import fs from 'node:fs';
import path from 'node:path';

import { Hono } from 'hono';

// 初始化 LibSQL 客户端 (Docker/Node 环境下的 SQLite)
const dbUrl = process.env.DATABASE_URL || 'file:./data/shortlinks.db';

import { execSync } from 'child_process';

// 确保目录存在
if (dbUrl.startsWith('file:')) {
  const dbPath = dbUrl.slice(5);
  const dir = path.dirname(dbPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  // 自动同步数据库结构 (Auto-Migration)
  try {
    // 使用本地安装的 drizzle-kit 进行同步
    const cmd = process.platform === 'win32' ? 'pnpm.cmd drizzle-kit push' : 'pnpm drizzle-kit push';
    execSync(cmd, { stdio: 'inherit' });
  } catch (error) {
  }
}

const client = createClient({
  url: dbUrl,
});

// 创建一个新的 Hono 实例作为根服务，用于控制中间件顺序
const server = new Hono();

// 1. 注入环境变量和 DB (最优先)
server.use('*', async (c, next) => {
  // Polyfill ASSETS.fetch 用于 index.html 和 admin.html 的加载
  const assetsFetcher = {
    fetch: async (request: Request) => {
      try {
        const url = new URL(request.url);
        // 主程序中请求的是 mock URL (e.g. https://placeholder/index.html)
        // 我们只需要文件名
        const filename = path.basename(url.pathname);
        const filePath = path.resolve('./static', filename);
        
        if (fs.existsSync(filePath)) {
           const content = fs.readFileSync(filePath);
           // 简单设置 HTML 类型，其他类型通常由 serveStatic 处理
           return new Response(content, {
             headers: { 'Content-Type': 'text/html; charset=utf-8' }
           });
        }
        return new Response('Not found', { status: 404 });
      } catch (e) {
        throw e;
      }
    }
  };

  // @ts-ignore
  c.env = {
    ...(c.env || {}),
    ...(process.env as any),
    DB: client,
    ASSETS: assetsFetcher,
  };
  await next();
});

// 2. 静态文件服务 (优先于应用路由)
// 这样请求 /shortlink.png 会先被这里拦截，不会落入 app 的 /:code 路由
server.use('/*', serveStatic({ root: path.resolve('./static') }));

server.route('/', app);

// 启动服务器
// 优先使用 PORT 环境变量，其次尝试从 BASE_URL 解析端口，默认 8000
let port = parseInt(process.env.PORT || '');
if (isNaN(port) && process.env.BASE_URL) {
  try {
    const url = new URL(process.env.BASE_URL);
    if (url.port) {
      port = parseInt(url.port);
    }
  } catch (e) {
    // 忽略 URL 解析错误
  }
}
if (isNaN(port)) {
  port = 8000;
}


import { cleanupExpiredLinks, cleanupTaskHook, getMsUntilNextBeijingMidnight } from './utils';

// Docker 每日定时清理管理 (零开销：精确计算 + 仅在开启时执行)
let cleanupTimeout: any = null;

async function manageCleanupTask() {
  // 销毁旧闹钟
  if (cleanupTimeout) {
    clearTimeout(cleanupTimeout);
    cleanupTimeout = null;
  }

  try {
    // 检查数据库开关
    const result = await client.execute({
      sql: 'SELECT value FROM system_config WHERE key = ?',
      args: ['cleanup_enabled']
    });
    const config = result.rows[0];

    if (config?.value === 'true') {
      const ms = getMsUntilNextBeijingMidnight();
      console.log(`[Cleanup Manager] 定时任务已启用，将在 ${Math.round(ms / 1000 / 60)} 分钟后触发清理`);
      
      cleanupTimeout = setTimeout(async () => {
        console.log(`[Cleanup Manager] 0 点已到，开始每日清理...`);
        const count = await cleanupExpiredLinks(client);
        console.log(`[Cleanup Manager] 清理完成，删除了 ${count} 条记录`);
        // 安排明天的清理
        manageCleanupTask();
      }, ms);
    } else {
      console.log(`[Cleanup Manager] 定时任务已禁用，后台已进入静默运行模式`);
    }
  } catch (err) {
    console.error('[Cleanup Manager] 任务管理出错:', err);
  }
}

// 注册钩子，让 API 可以实时控制后台任务
cleanupTaskHook.refresh = manageCleanupTask;

// 启动时初始化任务
manageCleanupTask();

serve({
  fetch: server.fetch,
  port,
});

