/**
 * 生成唯一的短码
 */
export function getUniqueShortCode(length: number = 6): string {
  const characters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let result = '';
  const randomBytes = new Uint8Array(length);
  crypto.getRandomValues(randomBytes);
  
  for (let i = 0; i < length; i++) {
    result += characters[randomBytes[i] % characters.length];
  }
  
  return result;
}

/**
 * 规范化 URL
 */
export function normalizeUrl(url: string): string {
  // 移除首尾空格
  url = url.trim();
  
  // 修复无效的转义序列（保留有效的）
  url = url.replace(/\\([^"\\/bfnrtu0-9])/g, '$1');
  
  // URL 解码
  try {
    url = decodeURIComponent(url);
  } catch {
    // 如果解码失败，使用原始 URL
  }
  
  // 确保有协议
  if (!url.match(/^https?:\/\//i)) {
    url = 'https://' + url;
  }
  
  return url;
}

/**
 * 验证 URL 格式
 */
export function validateUrl(url: string): boolean {
  try {
    const urlObj = new URL(url);
    return ['http:', 'https:'].includes(urlObj.protocol);
  } catch {
    return false;
  }
}

/**
 * 计算 URL 的 MD5 哈希
 */
export async function hashUrl(url: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(url);
  const hashBuffer = await crypto.subtle.digest('MD5', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * 获取客户端 IP
 */
export function getClientIP(request: Request): string {
  // 优先从 CF-Connecting-IP 获取（Cloudflare 专用）
  const cfIP = request.headers.get('CF-Connecting-IP');
  if (cfIP) return cfIP;
  
  // 其次从 X-Forwarded-For 获取
  const forwarded = request.headers.get('X-Forwarded-For');
  if (forwarded) {
    return forwarded.split(',')[0].trim();
  }
  
  // 最后从 X-Real-IP 获取
  const realIP = request.headers.get('X-Real-IP');
  if (realIP) return realIP;
  
  return 'unknown';
}

/**
 * 生成随机字符串
 */
export function generateRandomString(length: number): string {
  const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz0123456789-_';
  let result = '';
  const randomBytes = new Uint8Array(length);
  crypto.getRandomValues(randomBytes);
  
  for (let i = 0; i < length; i++) {
    result += characters[randomBytes[i] % characters.length];
  }
  
  return result;
}
