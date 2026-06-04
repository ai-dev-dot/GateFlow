import client from './client';
import type { ModelConfig, ProviderKey, PaginatedResponse } from '../types';

// ---- 模型配置 ----

/** 模型列表 */
export async function listModels(params?: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<ModelConfig>> {
  const res = await client.get('/gateway/models', { params });
  return res.data;
}

/** 创建模型 */
export async function createModel(data: Partial<ModelConfig>): Promise<ModelConfig> {
  const res = await client.post('/gateway/models', data);
  return res.data;
}

/** 更新模型 */
export async function updateModel(
  id: number,
  data: Partial<ModelConfig>,
): Promise<ModelConfig> {
  const res = await client.put(`/gateway/models/${id}`, data);
  return res.data;
}

/** 删除模型 */
export async function deleteModel(id: number): Promise<void> {
  await client.delete(`/gateway/models/${id}`);
}

// ---- Provider Key ----

/** Provider Key 列表 */
export async function listProviderKeys(params?: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<ProviderKey>> {
  const res = await client.get('/gateway/provider-keys', { params });
  return res.data;
}

/** 创建 Provider Key */
export async function createProviderKey(data: {
  provider: string;
  name: string;
  api_key: string;
  base_url?: string;
}): Promise<ProviderKey> {
  const res = await client.post('/gateway/provider-keys', data);
  return res.data;
}

/** 更新 Provider Key */
export async function updateProviderKey(
  id: number,
  data: Partial<Pick<ProviderKey, 'name' | 'is_active' | 'base_url'>>,
): Promise<ProviderKey> {
  const res = await client.put(`/gateway/provider-keys/${id}`, data);
  return res.data;
}

/** 删除 Provider Key */
export async function deleteProviderKey(id: number): Promise<void> {
  await client.delete(`/gateway/provider-keys/${id}`);
}

/** 重置 Provider Key */
export async function resetProviderKey(
  id: number,
  data: { api_key: string },
): Promise<ProviderKey> {
  const res = await client.post(`/gateway/provider-keys/${id}/reset`, data);
  return res.data;
}
