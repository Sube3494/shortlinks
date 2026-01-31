import { z } from 'zod';

// 短链创建请求
export const shortLinkCreateSchema = z.object({
  url: z.string().url('无效的URL格式'),
  custom_code: z.string().min(4).max(10).regex(/^[a-zA-Z0-9]+$/).optional(),
  expires_in_days: z.number().positive().optional(),
  expires_in_hours: z.number().positive().optional(),
  expires_in_minutes: z.number().positive().optional(),
});

export type ShortLinkCreate = z.infer<typeof shortLinkCreateSchema>;

// 批量短链创建请求
export const batchShortLinkCreateSchema = z.object({
  urls: z.array(z.string().url()),
  expires_in_days: z.number().positive().optional(),
  expires_in_hours: z.number().positive().optional(),
  expires_in_minutes: z.number().positive().optional(),
});

export type BatchShortLinkCreate = z.infer<typeof batchShortLinkCreateSchema>;

// 短链响应
export const shortLinkResponseSchema = z.object({
  short_code: z.string(),
  short_url: z.string(),
  original_url: z.string(),
  created_at: z.date(),
  click_count: z.number(),
  last_accessed: z.date().nullable(),
  expires_at: z.date().nullable(),
});

export type ShortLinkResponse = z.infer<typeof shortLinkResponseSchema>;

// 短链更新请求
export const shortLinkUpdateSchema = z.object({
  original_url: z.string().url().optional(),
  expires_in_days: z.number().positive().optional(),
  expires_in_hours: z.number().positive().optional(),
  expires_in_minutes: z.number().positive().optional(),
});

export type ShortLinkUpdate = z.infer<typeof shortLinkUpdateSchema>;

// API Key 创建请求
export const apiKeyCreateSchema = z.object({
  name: z.string().min(1, '名称不能为空'),
  expires_days: z.number().min(0).optional(),
  expires_in_minutes: z.number().min(0).optional(),
});

export type APIKeyCreate = z.infer<typeof apiKeyCreateSchema>;

// API Key 更新请求
export const apiKeyUpdateSchema = z.object({
  name: z.string().min(1).optional(),
  expires_days: z.number().positive().optional(),
  is_active: z.boolean().optional(),
});

export type APIKeyUpdate = z.infer<typeof apiKeyUpdateSchema>;

// 清理配置更新
export const cleanupConfigUpdateSchema = z.object({
  enabled: z.boolean().optional(),
  schedule_hour: z.number().min(0).max(23).optional(),
  schedule_minute: z.number().min(0).max(59).optional(),
});

export type CleanupConfigUpdate = z.infer<typeof cleanupConfigUpdateSchema>;
