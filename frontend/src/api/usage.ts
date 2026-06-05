import client from './client';
import type { UsageSummaryResponse } from '../types';

/** 管理员：按维度获取全局用量统计摘要 */
export async function getSummary(params: {
  dimension: 'model' | 'department' | 'user' | 'api_key';
  start_date?: string;
  end_date?: string;
}): Promise<UsageSummaryResponse> {
  const res = await client.get('/usage/summary', { params });
  return res.data;
}

/** 普通用户：获取自己的用量统计摘要 */
export async function getMySummary(params: {
  dimension?: 'model' | 'api_key';
  start_date?: string;
  end_date?: string;
}): Promise<UsageSummaryResponse> {
  const res = await client.get('/usage/my-summary', { params });
  return res.data;
}

/** 普通用户：获取自己的用量趋势 */
export async function getMyTrend(params?: {
  start_date?: string;
  end_date?: string;
}): Promise<{ data: { date: string; request_count: number; input_tokens: number; output_tokens: number; total_tokens: number }[] }> {
  const res = await client.get('/usage/my-trend', { params });
  return res.data;
}
