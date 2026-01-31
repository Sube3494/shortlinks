import { Hono, Context } from 'hono';
import { cors } from 'hono/cors';
import { eq, and, desc, sql, inArray } from 'drizzle-orm';
import { getDB } from './db';
import { shortlinks, apiKeys } from './db/schema';
import { verifyAPIKey, verifyAdminKey } from './middleware/auth';
import {
  shortLinkCreateSchema,
  batchShortLinkCreateSchema,
  shortLinkUpdateSchema,
  apiKeyCreateSchema,
  apiKeyUpdateSchema,
} from './types';
import {
  getUniqueShortCode,
  normalizeUrl,
  validateUrl,
  hashUrl,
  generateRandomString,
  cleanupExpiredLinks,
  cleanupTaskHook,
} from './utils';

type Bindings = {
  DB: D1Database;
  ASSETS: Fetcher;
  ADMIN_KEY: string;
  ADMIN_PATH?: string;
  BASE_URL?: string;
};

type Variables = {
  keyId: number | null;
};

export const app = new Hono<{ Bindings: Bindings; Variables: Variables }>();

// CORS 中间件
app.use('*', cors());

// 解析 BASE_URL
function resolveBaseURL(c: Context): string {
  // 1. 优先使用环境变量
  if (c.env.BASE_URL) {
    return c.env.BASE_URL.replace(/\/$/, '');
  }
  
  // 2. 自动推导 (强制 HTTPS)
  const host = c.req.header('host');
  if (host) {
    return `https://${host}`;
  }

  // 3. 最后的兜底 (通常不会执行到这里)
  const url = new URL(c.req.url);
  return `${url.protocol}//${url.host}`;
}

// 根路由 - 返回前端页面
app.get('/', async (c) => {
  try {
    const response = await c.env.ASSETS.fetch(new Request('https://placeholder/index.html'));
    return response;
  } catch {
    return c.text('短链服务', 200);
  }
});

// 管理后台页面
// 管理后台路由处理 (支持动态 ADMIN_PATH)
app.use('*', async (c, next) => {
  const url = new URL(c.req.url);
  // 获取 URL path，去掉首尾 /，确保能匹配自定义路径
  const path = url.pathname.replace(/^\/+|\/+$/g, '');
  
  // 严格使用环境变量，如果未设置则默认为 'admin'
  const adminPathEnv = (c.env.ADMIN_PATH || 'admin').replace(/^\/+|\/+$/g, '');
  
  // 如果配置了自定义路径，严禁通过默认 'admin'、'admin.html' 或内部模板路径访问
  // 使用 403 而非 404 是为了防止 wrangler/cloudflare 自动回退到静态资源服务 (Clean URLs)
  const isDefaultPath = path === 'admin' || path === 'admin.html' || path === '_admin_ui_.html';
  if (isDefaultPath && adminPathEnv !== 'admin') {
    try {
      const response = await c.env.ASSETS.fetch(new Request(new URL('/error.html?type=not_found', url.origin)));
      return response;
    } catch {
      return c.text('Not Found', 404);
    }
  }

  if (path === adminPathEnv) {
    try {
      // 构造 internal assets 请求 (使用隐藏的文件名防止绕过)
      const assetUrl = new URL('/_admin_ui_.html', url.origin);
      const response = await c.env.ASSETS.fetch(new Request(assetUrl));
      if (response.status >= 200 && response.status < 300) {
        return response;
      }
    } catch {
      // Fallback
    }
    return c.text('管理后台', 200);
  }

  await next();
});

// API: 获取当前 Key 信息
app.get('/api/key/info', verifyAPIKey, async (c) => {
  const keyId = c.get('keyId') as number | null;
  
  if (!keyId) {
    return c.json({
      authenticated: false,
      message: '服务未启用认证',
    });
  }
  
  const db = await getDB(c.env.DB);
  const hasKeysResult = await db
    .select()
    .from(apiKeys)
    .where(eq(apiKeys.isActive, true))
    .limit(1);
  
  const hasKeys = hasKeysResult.length > 0;
  
  const [apiKey] = await db
    .select()
    .from(apiKeys)
    .where(eq(apiKeys.id, keyId))
    .limit(1);
  
  if (!apiKey) {
    return c.json({ error: 'Key 不存在' }, 404);
  }
  
  return c.json({
    authenticated: true,
    name: apiKey.name,
    created_at: apiKey.createdAt,
    expires_at: apiKey.expiresAt,
    is_expired: apiKey.expiresAt ? new Date() > apiKey.expiresAt : false,
    usage_count: apiKey.usageCount,
    last_used_at: apiKey.lastUsedAt,
  });
});

// API: 创建短链
app.post('/api/shorten', verifyAPIKey, async (c) => {
  const body = await c.req.json();
  const validation = shortLinkCreateSchema.safeParse(body);
  
  if (!validation.success) {
    return c.json({ error: validation.error.errors[0].message }, 400);
  }
  
  const data = validation.data;
  const baseURL = resolveBaseURL(c);
  const db = await getDB(c.env.DB);
  const keyId = c.get('keyId') as number | null;
  
  // 规范化 URL
  const originalUrl = normalizeUrl(data.url);
  if (!validateUrl(originalUrl)) {
    return c.json({ error: '无效的URL格式' }, 400);
  }
  
  // 计算 URL 哈希
  const urlHash = await hashUrl(originalUrl);
  
  // 检查是否已存在
  const [existing] = await db
    .select()
    .from(shortlinks)
    .where(eq(shortlinks.urlHash, urlHash))
    .limit(1);
  
  if (existing) {
    // 检查是否过期
    if (existing.expiresAt && new Date() > existing.expiresAt) {
      await db.delete(shortlinks).where(eq(shortlinks.id, existing.id));
    } else {
      return c.json({
        short_code: existing.shortCode,
        short_url: `${baseURL}/${existing.shortCode}`,
        original_url: existing.originalUrl,
        title: existing.title,
        created_at: existing.createdAt,
        click_count: existing.clickCount,
        last_accessed: existing.lastAccessed,
        expires_at: existing.expiresAt,
      });
    }
  }
  
  // 生成短码
  let shortCode: string;
  if (data.custom_code) {
    const [existingCode] = await db
      .select()
      .from(shortlinks)
      .where(eq(shortlinks.shortCode, data.custom_code))
      .limit(1);
    
    if (existingCode) {
      return c.json({ error: `短码 '${data.custom_code}' 已被使用` }, 409);
    }
    shortCode = data.custom_code;
  } else {
    shortCode = getUniqueShortCode();
  }
  
  // 计算过期时间
  let expiresAt: Date | null = null;
  if (data.expires_in_days) {
    expiresAt = new Date(Date.now() + data.expires_in_days * 24 * 60 * 60 * 1000);
  } else if (data.expires_in_hours) {
    expiresAt = new Date(Date.now() + data.expires_in_hours * 60 * 60 * 1000);
  } else if (data.expires_in_minutes) {
    expiresAt = new Date(Date.now() + data.expires_in_minutes * 60 * 1000);
  }
  
  // 创建短链
  const result = await db
    .insert(shortlinks)
    .values({
      shortCode,
      originalUrl,
      urlHash,
      expiresAt,
      createdByKeyId: keyId,
      title: data.title,
    })
    .returning();
  
  const newLink = result[0];
  
  // 更新使用统计（仅在生成成功后）
  if (keyId) {
    db.update(apiKeys)
      .set({
        lastUsedAt: new Date(),
        usageCount: sql`${apiKeys.usageCount} + 1`,
      })
      .where(eq(apiKeys.id, keyId))
      .run();
  }

  return c.json({
    short_code: newLink.shortCode,
    short_url: `${baseURL}/${newLink.shortCode}`,
    original_url: newLink.originalUrl,
    title: newLink.title,
    created_at: newLink.createdAt,
    click_count: newLink.clickCount,
    last_accessed: newLink.lastAccessed,
    expires_at: newLink.expiresAt,
  });
});

// API: 批量创建短链
app.post('/api/shorten/batch', verifyAPIKey, async (c) => {
  const body = await c.req.json();
  const validation = batchShortLinkCreateSchema.safeParse(body);
  
  if (!validation.success) {
    return c.json({ error: validation.error.errors[0].message }, 400);
  }
  
  const data = validation.data;
  const baseURL = resolveBaseURL(c);
  const db = await getDB(c.env.DB);
  const keyId = c.get('keyId') as number | null;
  const results = [];
  
  for (const url of data.urls) {
    try {
      const originalUrl = normalizeUrl(url);
      if (!validateUrl(originalUrl)) continue;
      
      const urlHash = await hashUrl(originalUrl);
      const [existing] = await db
        .select()
        .from(shortlinks)
        .where(eq(shortlinks.urlHash, urlHash))
        .limit(1);
      
      if (existing && (!existing.expiresAt || new Date() <= existing.expiresAt)) {
        results.push({
          short_code: existing.shortCode,
          short_url: `${baseURL}/${existing.shortCode}`,
          original_url: existing.originalUrl,
          title: existing.title,
          created_at: existing.createdAt,
          click_count: existing.clickCount,
          last_accessed: existing.lastAccessed,
          expires_at: existing.expiresAt,
        });
        continue;
      }
      
      const shortCode = getUniqueShortCode();
      let expiresAt: Date | null = null;
      if (data.expires_in_days) {
        expiresAt = new Date(Date.now() + data.expires_in_days * 24 * 60 * 60 * 1000);
      } else if (data.expires_in_hours) {
        expiresAt = new Date(Date.now() + data.expires_in_hours * 60 * 60 * 1000);
      } else if (data.expires_in_minutes) {
        expiresAt = new Date(Date.now() + data.expires_in_minutes * 60 * 1000);
      }
      
      const result = await db
        .insert(shortlinks)
        .values({
          shortCode,
          originalUrl,
          urlHash,
          expiresAt,
          createdByKeyId: keyId,
          title: data.title,
        })
        .returning();
      
      const newLink = result[0];
      
      results.push({
        short_code: newLink.shortCode,
        short_url: `${baseURL}/${newLink.shortCode}`,
        original_url: newLink.originalUrl,
        title: newLink.title,
        created_at: newLink.createdAt,
        click_count: newLink.clickCount,
        last_accessed: newLink.lastAccessed,
        expires_at: newLink.expiresAt,
      });
    } catch (error) {
    }
  }
  
  // 更新使用统计（按创建成功的数量计次）
  if (keyId && results.length > 0) {
    db.update(apiKeys)
      .set({
        lastUsedAt: new Date(),
        usageCount: sql`${apiKeys.usageCount} + ${results.length}`,
      })
      .where(eq(apiKeys.id, keyId))
      .run();
  }

  return c.json(results);
});

// 短链重定向
app.get('/:code', async (c) => {
  const code = c.req.param('code');
  const db = await getDB(c.env.DB);
  
  // 检查是否为站长验证文件
  if (code.endsWith('.txt')) {
    return c.text('', 404);
  }
  
  const [link] = await db
    .select()
    .from(shortlinks)
    .where(eq(shortlinks.shortCode, code))
    .limit(1);
  
  if (!link) {
    try {
      const response = await c.env.ASSETS.fetch(
        new Request('https://placeholder/error.html?type=not_found')
      );
      return response;
    } catch {
      return c.text('短链不存在', 404);
    }
  }
  
  // 检查过期
  if (link.expiresAt && new Date() > link.expiresAt) {
    await db.delete(shortlinks).where(eq(shortlinks.id, link.id));
    try {
      const response = await c.env.ASSETS.fetch(
        new Request('https://placeholder/error.html?type=expired')
      );
      return response;
    } catch {
      return c.text('短链已过期', 410);
    }
  }
  
  // 更新统计
  await db
    .update(shortlinks)
    .set({
      clickCount: link.clickCount + 1,
      lastAccessed: new Date(),
    })
    .where(eq(shortlinks.id, link.id));
  
  return c.redirect(link.originalUrl, 302);
});

// API: 获取短链信息
app.get('/api/info/:code', verifyAPIKey, async (c) => {
  const code = c.req.param('code');
  const db = await getDB(c.env.DB);
  const keyId = c.get('keyId') as number | null;
  
  const [link] = await db
    .select()
    .from(shortlinks)
    .where(eq(shortlinks.shortCode, code))
    .limit(1);
  
  if (!link) {
    return c.json({ error: '短链不存在' }, 404);
  }
  
  // 权限检查
  if (keyId && link.createdByKeyId !== keyId) {
    return c.json({ error: '无权查看此短链' }, 403);
  }
  
  const baseURL = resolveBaseURL(c);
  return c.json({
    short_code: link.shortCode,
    short_url: `${baseURL}/${link.shortCode}`,
    original_url: link.originalUrl,
    title: link.title,
    created_at: link.createdAt,
    click_count: link.clickCount,
    last_accessed: link.lastAccessed,
    expires_at: link.expiresAt,
  });
});

// API: 批量删除短链
app.post('/api/delete/batch', verifyAPIKey, async (c) => {
  const body = await c.req.json();
  const codes = body.codes;
  
  if (!Array.isArray(codes) || codes.length === 0) {
    return c.json({ error: '无效的短码列表' }, 400);
  }
  
  const db = await getDB(c.env.DB);
  const keyId = c.get('keyId') as number | null;
  
  // 如果有认证，限制只能删除自己创建的
  const conditions = [inArray(shortlinks.shortCode, codes)];
  if (keyId) {
    conditions.push(eq(shortlinks.createdByKeyId, keyId));
  }
  
  await db.delete(shortlinks).where(and(...conditions));
  
  return c.json({ message: `成功删除 ${codes.length} 条记录` });
});

// API: 列出所有短链
app.get('/api/list', verifyAPIKey, async (c) => {
  const db = await getDB(c.env.DB);
  const keyId = c.get('keyId') as number | null;
  const baseURL = resolveBaseURL(c);
  
  // 获取分页参数
  const skip = parseInt(c.req.query('skip') || '0');
  const limit = Math.min(parseInt(c.req.query('limit') || '20'), 100);
  
  // 只显示自己创建的
  const query = keyId
    ? db.select().from(shortlinks)
        .where(eq(shortlinks.createdByKeyId, keyId))
        .orderBy(desc(shortlinks.createdAt))
    : db.select().from(shortlinks)
        .orderBy(desc(shortlinks.createdAt));

  const links = await query.offset(skip).limit(limit);
  
  return c.json(
    links.map((link: any) => ({
      short_code: link.shortCode,
      short_url: `${baseURL}/${link.shortCode}`,
      original_url: link.originalUrl,
      title: link.title,
      created_at: link.createdAt,
      click_count: link.clickCount,
      last_accessed: link.lastAccessed,
      expires_at: link.expiresAt,
    }))
  );
});

// API: 删除短链
app.delete('/api/:code', verifyAPIKey, async (c) => {
  const code = c.req.param('code');
  const db = await getDB(c.env.DB);
  const keyId = c.get('keyId') as number | null;
  
  const [link] = await db
    .select()
    .from(shortlinks)
    .where(eq(shortlinks.shortCode, code))
    .limit(1);
  
  if (!link) {
    return c.json({ error: '短链不存在' }, 404);
  }
  
  // 权限检查
  if (keyId && link.createdByKeyId !== keyId) {
    return c.json({ error: '无权删除此短链' }, 403);
  }
  
  await db.delete(shortlinks).where(eq(shortlinks.id, link.id));
  
  return c.json({ message: '删除成功' });
});

// 管理员 API: 创建 API Key
app.post('/api/admin/keys/create', verifyAdminKey, async (c) => {
  const body = await c.req.json();
  
  const validation = apiKeyCreateSchema.safeParse(body);
  
  if (!validation.success) {
    return c.json({ error: validation.error.errors[0].message }, 400);
  }
  
  const data = validation.data;
  const db = await getDB(c.env.DB);
  
  const key = generateRandomString(43);
  let expiresAt: Date | null = null;
  if (data.expires_days) {
    expiresAt = new Date(Date.now() + data.expires_days * 24 * 60 * 60 * 1000);
  } else if (data.expires_in_minutes) {
    expiresAt = new Date(Date.now() + data.expires_in_minutes * 60 * 1000);
  }
  
  const [newKey] = await db
    .insert(apiKeys)
    .values({
      key,
      name: data.name,
      expiresAt,
    })
    .returning();
  
  return c.json({
    id: newKey.id,
    key: newKey.key,
    name: newKey.name,
    created_at: newKey.createdAt,
    expires_at: newKey.expiresAt,
  });
});

// 管理员 API: 列出所有 Keys
app.get('/api/admin/keys/list', verifyAdminKey, async (c) => {
  const db = await getDB(c.env.DB);
  const keys = await db.select().from(apiKeys).orderBy(desc(apiKeys.createdAt));
  
  return c.json({
    keys: keys.map((k: any) => ({
      id: k.id,
      key: k.key,
      name: k.name,
      created_at: k.createdAt,
      expires_at: k.expiresAt,
      last_used_at: k.lastUsedAt,
      usage_count: k.usageCount,
      is_active: k.isActive,
    }))
  });
});

import { systemConfig } from './db/schema';

// 管理员 API: 获取清理开关状态
app.get('/api/admin/cleanup/config', verifyAdminKey, async (c) => {
  const db = await getDB(c.env.DB);
  const [config] = await db.select().from(systemConfig).where(eq(systemConfig.key, 'cleanup_enabled')).limit(1);
  return c.json({ enabled: config?.value === 'true' });
});

// 管理员 API: 更新清理开关状态
app.put('/api/admin/cleanup/config', verifyAdminKey, async (c) => {
  const body = await c.req.json();
  const db = await getDB(c.env.DB);
  
  await db.insert(systemConfig)
    .values({ key: 'cleanup_enabled', value: String(body.enabled), description: '自动清理开关' })
    .onConflictDoUpdate({ target: systemConfig.key, set: { value: String(body.enabled), updatedAt: new Date() } });
  
  // 通知后台任务更新清理状态
  cleanupTaskHook.refresh();
  
  return c.json({ message: '配置已更新' });
});


// 管理员 API: 手动触发清理 (保留以供测试)
app.post('/api/admin/cleanup/trigger', verifyAdminKey, async (c) => {
  const db = await getDB(c.env.DB);
  const deletedCount = await cleanupExpiredLinks(db);
  return c.json({ deleted_count: deletedCount, message: '清理完成' });
});

// 管理员 API: 切换 Key 状态
app.patch('/api/admin/keys/:id/toggle', verifyAdminKey, async (c) => {
  const id = parseInt(c.req.param('id'));
  const db = await getDB(c.env.DB);
  
  const [key] = await db.select().from(apiKeys).where(eq(apiKeys.id, id)).limit(1);
  if (!key) return c.json({ error: 'Key 不存在' }, 404);
  
  const newStatus = !key.isActive;
  await db.update(apiKeys).set({ isActive: newStatus }).where(eq(apiKeys.id, id));
  
  return c.json({ 
    message: newStatus ? 'Key 已启用' : 'Key 已禁用', 
    is_active: newStatus 
  });
});

// API: 获取短链统计
app.get('/api/stats/:code', async (c) => {
  const code = c.req.param('code');
  const db = await getDB(c.env.DB);
  
  const [link] = await db
    .select()
    .from(shortlinks)
    .where(eq(shortlinks.shortCode, code))
    .limit(1);
  
  if (!link) return c.json({ error: '短链不存在' }, 404);
  
   return c.json({
    short_code: link.shortCode,
    original_url: link.originalUrl,
    created_at: link.createdAt,
    click_count: link.clickCount,
    last_accessed: link.lastAccessed,
    expires_at: link.expiresAt
  });
});

// 管理员 API: 删除 Key
app.delete('/api/admin/keys/:id', verifyAdminKey, async (c) => {
  const id = parseInt(c.req.param('id'));
  const db = await getDB(c.env.DB);
  
  await db.delete(apiKeys).where(eq(apiKeys.id, id));
  
  return c.json({ message: '删除成功' });
});

export default {
  fetch: app.fetch,
  async scheduled(event: ScheduledEvent, env: Bindings, ctx: ExecutionContext) {
    const db = await getDB(env.DB);
    
    // 1. 检查开关状态
    const [config] = await db
      .select()
      .from(systemConfig)
      .where(eq(systemConfig.key, 'cleanup_enabled'))
      .limit(1);
    
    // 2. 只有开启状态才执行 (Cron 已经设定在 0 点)
    if (config?.value === 'true') {
      ctx.waitUntil(cleanupExpiredLinks(db));
    }
  }
};
