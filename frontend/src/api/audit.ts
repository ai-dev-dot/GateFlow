import client from './client';
import type { AuditLog, PaginatedResponse } from '../types';

/** LLM 调用日志列表 */
export async function listAuditLogs(params?: {
  page?: number;
  page_size?: number;
  action?: string;
  resource_type?: string;
  user_id?: number;
  model?: string;
  start_date?: string;
  end_date?: string;
}): Promise<PaginatedResponse<AuditLog>> {
  const res = await client.get('/audit/logs', { params });
  return res.data;
}

/** LLM 调用日志列表 (别名) */
export const listLogs = listAuditLogs;
