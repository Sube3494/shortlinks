/*
 * @Date: 2026-01-09 20:12:01
 * @Author: Sube
 * @FilePath: drizzle.config.ts
 * @LastEditTime: 2026-01-09 22:21:58
 * @Description: 
 */
import { defineConfig } from 'drizzle-kit';
import 'dotenv/config';

export default defineConfig({
  schema: './src/db/schema.ts',
  out: './drizzle/migrations',
  dialect: 'sqlite',
  ...(process.env.DATABASE_URL
    ? {
        dbCredentials: {
          url: process.env.DATABASE_URL,
        },
      }
    : {
        driver: 'd1-http',
      }),
});
