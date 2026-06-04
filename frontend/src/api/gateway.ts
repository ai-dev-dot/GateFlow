import client from './client';
import type { ModelConfig, ProviderKey } from '../types';

// ---- 模型配置 ----

/** 模型列表（后端返回数组） */
export async function listModels(): Promise<ModelConfig[]> {
  const res = await client.get('/gateway/models');
  return res.data;
}

/** 创建模型 */
export async function createModel(data: Partial<ModelConfig>): Promise<ModelConfig> {
  const res = await client.post('/gateway/models', data);
  return res.data;
}

/** 更新模型 */
export async function updateModel(
  id: string,
  data: Partial<ModelConfig>,
): Promise<ModelConfig> {
  const res = await client.put(`/gateway/models/${id}`, data);
  return res.data;
}

/** 删除模型 */
export async function deleteModel(id: string): Promise<void> {
  await client.delete(`/gateway/models/${id}`);
}

// ---- Provider Key ----

/** Provider Key 列表（后端返回数组） */
export async function listProviderKeys(): Promise<ProviderKey[]> {
  const res = await client.get('/gateway/provider-keys');
  return res.data;
}

/** 创建 Provider Key */
export async function createProviderKey(data: {
  provider: string;
  name: string;
  key: string;
  remark?: string;
}): Promise<ProviderKey> {
  const res = await client.post('/gateway/provider-keys', data);
  return res.data;
}

/** 更新 Provider Key */
export async function updateProviderKey(
  id: string,
  data: Partial<Pick<ProviderKey, 'name' | 'is_active' | 'remark' | 'rpm_limit' | 'tpm_limit'>>,
): Promise<ProviderKey> {
  const res = await client.put(`/gateway/provider-keys/${id}`, data);
  return res.data;
}

/** 删除 Provider Key */
export async function deleteProviderKey(id: string): Promise<void> {
  await client.delete(`/gateway/provider-keys/${id}`);
}

/** 重置 Provider Key */
export async function resetProviderKey(
  id: string,
  data: { api_key: string },
): Promise<ProviderKey> {
  const res = await client.post(`/gateway/provider-keys/${id}/reset`, data);
  return res.data;
}
