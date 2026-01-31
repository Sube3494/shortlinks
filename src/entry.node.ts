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

const client = createClient({
  url: dbUrl,
});

// 确保数据库准备就绪的异步逻辑
async function initializeDatabase() {
  if (dbUrl.startsWith('file:')) {
    const dbPath = dbUrl.slice(5);
    const dir = path.dirname(dbPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // 自动同步数据库结构 (Auto-Migration)
    try {
      console.log('[Database] 正在同步数据库结构...');
      const cmd = process.platform === 'win32' ? 'pnpm.cmd drizzle-kit push --force' : 'pnpm drizzle-kit push --force';
      execSync(cmd, { stdio: 'inherit' });
      console.log('[Database] 数据库结构同步完成');
    } catch (error) {
      console.error('[Database] 自动同步失败，尝试手动修复字段...', error);
      try {
        await client.execute({
          sql: 'ALTER TABLE shortlinks ADD COLUMN title TEXT',
          args: []
        });
        console.log('[Database] 手动补齐 title 字段完成');
      } catch (manualError: any) {
        if (manualError?.message?.includes('duplicate column name') || manualError?.message?.includes('already exists')) {
          console.log('[Database] 字段解析：title 字段已存在');
        } else {
          console.error('[Database] 手动修复失败:', manualError);
        }
      }
    }
  }
}

// 创建一个新的 Hono 实例作为根服务，用于控制中间件顺序
const server = new Hono();

// 1. 注入环境变量和 DB (最优先)
server.use('*', async (c, next) => {
  const assetsFetcher = {
    fetch: async (request: Request) => {
      try {
        const url = new URL(request.url);
        const filename = path.basename(url.pathname);
        const filePath = path.resolve('./static', filename);
        
        if (fs.existsSync(filePath)) {
           const content = fs.readFileSync(filePath);
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

// 2. 静态文件服务
server.use('/*', serveStatic({ root: path.resolve('./static') }));

server.route('/', app);

// 启动参数解析
let port = parseInt(process.env.PORT || '');
if (isNaN(port) && process.env.BASE_URL) {
  try {
    const url = new URL(process.env.BASE_URL);
    if (url.port) port = parseInt(url.port);
  } catch (e) {}
}
if (isNaN(port)) port = 8000;

import { cleanupExpiredLinks, cleanupTaskHook, getMsUntilNextBeijingMidnight } from './utils';
let cleanupTimeout: any = null;

async function manageCleanupTask() {
  if (cleanupTimeout) {
    clearTimeout(cleanupTimeout);
    cleanupTimeout = null;
  }

  try {
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
        manageCleanupTask();
      }, ms);
    } else {
      console.log(`[Cleanup Manager] 定时任务已禁用，后台已进入静默运行模式`);
    }
  } catch (err) {
    console.error('[Cleanup Manager] 任务管理出错:', err);
  }
}

cleanupTaskHook.refresh = manageCleanupTask;

// 统一启动入口
async function start() {
  await initializeDatabase();
  await manageCleanupTask();
  
  console.log(`[Server] 服务已启动，监听端口: ${port}`);
  serve({
    fetch: server.fetch,
    port,
  });
}

start().catch(err => {
  console.error('[Fatal] 服务启动失败:', err);
  process.exit(1);
});

