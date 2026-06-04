import client from './client';
import type { UsageSummary, UsageSummaryResponse } from '../types';

/** 用量统计摘要（旧接口，兼容） */
export async function getUsageSummary(params?: {
  start_date?: string;
  end_date?: string;
  user_id?: number;
  model_name?: string;
}): Promise<UsageSummary> {
  const res = await client.get('/usage/summary', { params });
  return res.data;
}

/** 按维度获取用量统计摘要 */
export async function getSummary(params: {
  dimension: 'model' | 'department' | 'user';
  start_date?: string;
  end_date?: string;
}): Promise<UsageSummaryResponse> {
  const res = await client.get('/usage/summary', { params });
  return res.data;
}
