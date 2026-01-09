import { drizzle as drizzleD1 } from 'drizzle-orm/d1';
import * as schema from './schema';

export async function getDB(db: any) {
  // 检查是否为 D1 绑定（通常在 Cloudflare 环境）
  if (db && typeof db.prepare === 'function' && typeof db.batch === 'function') {
    return drizzleD1(db, { schema });
  }
  
  // 否则假定为 LibSQL/SQLite 客户端（支持 Node.js 环境）
  // 使用动态导入，避免在 Cloudflare 环境下构建失败
  const { drizzle: drizzleLibsql } = await import('drizzle-orm/libsql');
  return drizzleLibsql(db, { schema });
}

export type DB = any; // 由于 getDB 变为异步，类型推导较复杂，先使用 any
