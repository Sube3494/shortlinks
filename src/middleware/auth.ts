import { Context, Next } from 'hono';
import { eq, and } from 'drizzle-orm';
import { apiKeys } from '../db/schema';
import { getDB } from '../db';

// IP 限流数据结构
interface IPFailureRecord {
  attempts: number[];
  banUntil: number | null;
}

const ipFailures = new Map<string, IPFailureRecord>();

const MAX_FAILURES = 5;
const FAILURE_WINDOW = 300000; // 5 分钟（毫秒）
const BAN_DURATION = 900000; // 15 分钟（毫秒）

/**
 * 检查 IP 是否被封禁
 */
function isIPBanned(ip: string): boolean {
  const record = ipFailures.get(ip);
  if (!record) return false;
  
  if (record.banUntil && Date.now() < record.banUntil) {
    return true;
  }
  
  // 解除过期的封禁
  if (record.banUntil && Date.now() >= record.banUntil) {
    record.banUntil = null;
    record.attempts = [];
  }
  
  return false;
}

/**
 * 记录认证失败
 */
function recordAuthFailure(ip: string): boolean {
  const now = Date.now();
  let record = ipFailures.get(ip);
  
  if (!record) {
    record = { attempts: [], banUntil: null };
    ipFailures.set(ip, record);
  }
  
  // 清理过期的失败记录
  record.attempts = record.attempts.filter(t => now - t < FAILURE_WINDOW);
  
  // 添加当前失败记录
  record.attempts.push(now);
  
  // 检查是否达到封禁阈值
  if (record.attempts.length >= MAX_FAILURES) {
    record.banUntil = now + BAN_DURATION;
    return true;
  }
  
  return false;
}

/**
 * 获取剩余封禁时间（秒）
 */
function getRemainingBanTime(ip: string): number {
  const record = ipFailures.get(ip);
  if (!record || !record.banUntil) return 0;
  
  const remaining = Math.floor((record.banUntil - Date.now()) / 1000);
  return Math.max(0, remaining);
}

/**
 * 获取客户端 IP
 */
function getClientIP(c: Context): string {
  const cfIP = c.req.header('CF-Connecting-IP');
  if (cfIP) return cfIP;
  
  const forwarded = c.req.header('X-Forwarded-For');
  if (forwarded) return forwarded.split(',')[0].trim();
  
  const realIP = c.req.header('X-Real-IP');
  if (realIP) return realIP;
  
  return 'unknown';
}

/**
 * API Key 认证中间件
 */
export async function verifyAPIKey(c: Context, next: Next) {
  const clientIP = getClientIP(c);
  
  // 检查 IP 是否被封禁
  if (isIPBanned(clientIP)) {
    const remaining = getRemainingBanTime(clientIP);
    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;
    return c.json({
      error: `由于多次认证失败,您的 IP 已被临时封禁。请在 ${minutes} 分 ${seconds} 秒后重试`
    }, 429);
  }
  
  // 获取提供的密钥
  const headerKey = c.req.header('X-API-Key');
  const queryKey = c.req.query('api_key');
  const providedKey = headerKey || queryKey;
  
  const db = await getDB(c.env.DB);
  
  // 如果提供了密钥，验证它
  if (providedKey) {
    const [dbKey] = await db
      .select()
      .from(apiKeys)
      .where(and(
        eq(apiKeys.key, providedKey),
        eq(apiKeys.isActive, true)
      ))
      .limit(1);
    
    if (dbKey) {
      // 检查是否过期
      if (dbKey.expiresAt && new Date() > dbKey.expiresAt) {
        recordAuthFailure(clientIP);
        return c.json({ error: 'API Key 已过期' }, 403);
      }
      
      // 更新使用统计（异步，不等待）
      db.update(apiKeys)
        .set({
          lastUsedAt: new Date(),
          usageCount: dbKey.usageCount + 1,
        })
        .where(eq(apiKeys.id, dbKey.id))
        .run();
      
      // 将 Key ID 存储到上下文
      c.set('keyId', dbKey.id);
      return next();
    } else {
      // 提供了密钥但无效
      recordAuthFailure(clientIP);
      return c.json({ error: '无效的API密钥' }, 403);
    }
  }
  
  // 强制开启认证：未提供密钥则拒绝访问
  return c.json({ error: '请提供有效的 API 密钥以使用服务' }, 401);
}

/**
 * 管理员认证中间件
 */
export async function verifyAdminKey(c: Context, next: Next) {
  const clientIP = getClientIP(c);
  
  // 检查 IP 封禁
  if (isIPBanned(clientIP)) {
    const remaining = getRemainingBanTime(clientIP);
    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;
    return c.json({
      error: `由于多次认证失败,您的 IP 已被临时封禁。请在 ${minutes} 分 ${seconds} 秒后重试`
    }, 429);
  }
  
  const headerKey = c.req.header('X-Admin-Key');
  const queryKey = c.req.query('admin_key');
  const providedKey = headerKey || queryKey;
  
  const adminKey = c.env.ADMIN_KEY;
  
  if (!adminKey) {
    return c.json({
      error: '管理功能未启用: 请设置 ADMIN_KEY 环境变量'
    }, 503);
  }
  
  if (!providedKey || providedKey !== adminKey) {
    recordAuthFailure(clientIP);
    
    if (isIPBanned(clientIP)) {
      return c.json({ error: '尝试次数过多，IP 已被封禁' }, 429);
    }
    
    return c.json({ error: '无效的管理员密钥' }, 403);
  }
  
  return next();
}
