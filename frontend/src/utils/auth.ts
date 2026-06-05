/** JWT payload 解码（纯 Base64，不验证签名） */
export function decodeToken(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split('.')[1]
    return JSON.parse(atob(payload))
  } catch {
    return null
  }
}

/** 从 token 提取用户信息 */
export function getUserFromToken(token: string) {
  const payload = decodeToken(token)
  if (!payload) return null
  const role = payload.role as string
  return {
    id: payload.sub as string,
    username: payload.username as string,
    role: role === 'admin' ? 'admin' as const : 'user' as const,
  }
}
