/*
 * @Date: 2026-01-09 20:12:01
 * @Author: Sube
 * @FilePath: drizzle.config.ts
 * @LastEditTime: 2026-01-09 22:21:58
 * @Description: 
 */
import { defineConfig } from 'drizzle-kit';
import 'dotenv/config';

const dbUrl = process.env.DATABASE_URL || 'file:./data/shortlinks.db';

export default defineConfig({
  schema: './src/db/schema.ts',
  out: './drizzle/migrations',
  dialect: 'sqlite',
  dbCredentials: {
    url: dbUrl,
  },
});
