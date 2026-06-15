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

const client = createClient({
  url: dbUrl,
});

const bootstrapStatements = [
  `CREATE TABLE IF NOT EXISTS api_keys (
    id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
    key text NOT NULL,
    name text NOT NULL,
    created_at integer DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at integer,
    last_used_at integer,
    usage_count integer DEFAULT 0 NOT NULL,
    is_active integer DEFAULT true NOT NULL
  )`,
  'CREATE UNIQUE INDEX IF NOT EXISTS api_keys_key_unique ON api_keys (key)',
  `CREATE TABLE IF NOT EXISTS shortlinks (
    id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
    short_code text NOT NULL,
    original_url text NOT NULL,
    url_hash text,
    created_at integer DEFAULT CURRENT_TIMESTAMP NOT NULL,
    click_count integer DEFAULT 0 NOT NULL,
    last_accessed integer,
    expires_at integer,
    created_by_key_id integer,
    title text
  )`,
  'CREATE UNIQUE INDEX IF NOT EXISTS shortlinks_short_code_unique ON shortlinks (short_code)',
  `CREATE TABLE IF NOT EXISTS system_config (
    id integer PRIMARY KEY AUTOINCREMENT NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    description text,
    updated_at integer DEFAULT CURRENT_TIMESTAMP NOT NULL
  )`,
  'CREATE UNIQUE INDEX IF NOT EXISTS system_config_key_unique ON system_config (key)',
];

async function columnExists(tableName: string, columnName: string) {
  const result = await client.execute(`PRAGMA table_info(${tableName})`);
  return result.rows.some((row: any) => row.name === columnName);
}

// 确保数据库准备就绪的异步逻辑
async function initializeDatabase() {
  if (dbUrl.startsWith('file:')) {
    const dbPath = dbUrl.slice(5);
    const dir = path.dirname(dbPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    try {
      console.log('[Database] 正在检查并同步本地 SQLite 结构...');
      for (const statement of bootstrapStatements) {
        await client.execute(statement);
      }

      if (!(await columnExists('shortlinks', 'title'))) {
        await client.execute('ALTER TABLE shortlinks ADD COLUMN title TEXT');
        console.log('[Database] 已为 shortlinks 补齐 title 字段');
      }

      console.log('[Database] 本地 SQLite 结构已就绪');
    } catch (error) {
      console.error('[Database] 本地 SQLite 结构同步失败:', error);
      throw error;
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

