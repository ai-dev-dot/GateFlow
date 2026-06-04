import client from './client';
import type { LoginRequest, TokenResponse } from '../types';

/** 登录 */
export async function login(data: LoginRequest): Promise<TokenResponse> {
  const res = await client.post<TokenResponse>('/auth/login', data);
  return res.data;
}

/** 刷新令牌 */
export async function refreshToken(): Promise<TokenResponse> {
  const refresh = localStorage.getItem('refresh_token');
  const res = await client.post<TokenResponse>('/auth/refresh', {
    refresh_token: refresh,
  });
  return res.data;
}

/** 修改密码 */
export async function changePassword(
  oldPassword: string,
  newPassword: string,
): Promise<void> {
  await client.put('/auth/password', {
    old_password: oldPassword,
    new_password: newPassword,
  });
}
