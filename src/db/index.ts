/*
 * @Date: 2026-01-09 20:12:00
 * @Author: Sube
 * @FilePath: index.ts
 * @LastEditTime: 2026-01-25 20:56:41
 * @Description: 
 */
import { drizzle as drizzleD1 } from 'drizzle-orm/d1';
import * as schema from './schema';

let cachedDB: any = null;

export async function getDB(db: any) {
  if (cachedDB) return cachedDB;

  // 检查是否为 D1 绑定（通常在 Cloudflare 环境）
  if (db && typeof db.prepare === 'function' && typeof db.batch === 'function') {
    cachedDB = drizzleD1(db, { schema });
    return cachedDB;
  }
  
  // 否则假定为 LibSQL/SQLite 客户端（支持 Node.js 环境）
  const { drizzle: drizzleLibsql } = await import('drizzle-orm/libsql');
  cachedDB = drizzleLibsql(db, { schema });
  return cachedDB;
}

export type DB = any; // 由于 getDB 变为异步，类型推导较复杂，先使用 any
