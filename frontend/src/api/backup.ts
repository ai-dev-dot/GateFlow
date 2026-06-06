import client from './client';
import type { BackupFileInfo, BackupResult, SystemConfig } from '../types';

/** 获取备份配置（单行 singleton） */
export async function getConfig(): Promise<SystemConfig> {
  const res = await client.get('/backup/config');
  return res.data;
}

/** 更新备份配置（partial update） */
export async function updateConfig(data: {
  backup_dir?: string;
  backup_include_audit_logs?: boolean;
  pg_dump_path?: string | null;
}): Promise<SystemConfig> {
  const res = await client.put('/backup/config', data);
  return res.data;
}

/** 触发一次备份（admin only，PG-only；SQLite 环境会 501） */
export async function runBackup(): Promise<BackupResult> {
  const res = await client.post('/backup/run');
  return res.data;
}

/** 列出历史备份文件，按 mtime 倒序 */
export async function listBackups(): Promise<BackupFileInfo[]> {
  const res = await client.get('/backup/history');
  return res.data;
}
