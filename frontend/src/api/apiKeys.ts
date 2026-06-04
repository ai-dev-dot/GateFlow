import client from './client';
import type { APIKey } from '../types';

/** API Key 列表（后端返回数组） */
export async function listAPIKeys(): Promise<APIKey[]> {
  const res = await client.get('/api-keys');
  return res.data;
}

/** 创建 API Key */
export async function createAPIKey(data: {
  name: string;
  permissions?: string[];
  rate_limit?: number;
  expires_at?: string;
}): Promise<APIKey> {
  const res = await client.post('/api-keys', data);
  return res.data;
}

/** 更新 API Key */
export async function updateAPIKey(
  id: string,
  data: Partial<Pick<APIKey, 'name' | 'is_active' | 'rate_limit' | 'expires_at'>>,
): Promise<APIKey> {
  const res = await client.put(`/api-keys/${id}`, data);
  return res.data;
}

/** 删除 API Key */
export async function deleteAPIKey(id: string): Promise<void> {
  await client.delete(`/api-keys/${id}`);
}
