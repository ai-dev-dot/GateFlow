// ============================================================
// GateFlow - TypeScript 类型定义
// ============================================================

// ---------------------
// 用户 / 角色 / 部门
// ---------------------

export interface Role {
  id: string;
  name: string;
  permissions?: string[];
}

export interface Department {
  id: string;
  name: string;
  parent_id?: string;
}

export interface User {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  department_id?: string;
  role_id?: string;
  created_at: string;
  last_login?: string;
}

// ---------------------
// API Key
// ---------------------

export interface APIKey {
  id: string;
  name: string;
  key: string;
  permissions?: string[];
  rate_limit: number;
  expires_at?: string;
  is_active: boolean;
  created_at: string;
  last_used_at?: string;
}

// ---------------------
// 网关 - Provider Key / Model
// ---------------------

export interface ProviderKey {
  id: string;
  provider: string;
  key: string;
  name: string;
  remark?: string;
  is_active: boolean;
  is_banned: boolean;
  ban_reason?: string;
  rpm_limit: number;
  tpm_limit: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  consecutive_errors: number;
  cool_down_until?: string;
  last_used_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ModelConfig {
  id: string;
  model_alias: string;
  provider: string;
  target_model: string;
  target_url: string;
  is_active: boolean;
  priority: number;
  default_temperature?: number;
  default_max_tokens?: number;
  created_at: string;
  updated_at: string;
}

// ---------------------
// 聊天 - 会话 / 消息
// ---------------------

export interface Conversation {
  id: string;
  title: string;
  model?: ModelConfig;
  user: User;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  tokens_used?: number;
  created_at: string;
}

// ---------------------
// LLM 调用日志
// ---------------------

export interface AuditLog {
  id: number;
  user?: User;
  action: string;
  resource_type: string;
  resource_id?: number;
  detail?: string;
  ip_address?: string;
  created_at: string;
  // 网关请求日志扩展字段
  model?: string;
  status?: string;
  request_tokens?: number;
  response_tokens?: number;
  latency_ms?: number;
  status_code?: number;
}

// ---------------------
// 用量统计
// ---------------------

export interface UsageSummaryItem {
  dimension: string;
  username?: string | null;  // 仅 dimension=user 时返回
  request_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface UsageSummaryResponse {
  dimension: string;
  items: UsageSummaryItem[];
}

// ---------------------
// 认证
// ---------------------

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// ---------------------
// 通用分页响应
// ---------------------

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ---------------------
// 数据库备份
// ---------------------

export interface SystemConfig {
  backup_dir: string | null;
  backup_include_audit_logs: boolean;
  pg_dump_path: string | null;
  updated_at: string;
}

export interface BackupResult {
  filename: string;
  size_bytes: number;
  duration_ms: number;
  tables_dumped: number;
  excluded_audit_logs: boolean;
  path: string;
  note: string | null;
}

export interface BackupFileInfo {
  filename: string;
  size_bytes: number;
  mtime: string;
  note: string | null;
}
