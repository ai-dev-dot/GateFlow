import client from './client';
import type { UsageSummary } from '../types';

/** 用量统计摘要 */
export async function getUsageSummary(params?: {
  start_date?: string;
  end_date?: string;
  user_id?: number;
  model_name?: string;
}): Promise<UsageSummary> {
  const res = await client.get('/usage/summary', { params });
  return res.data;
}
