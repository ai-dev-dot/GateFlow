// ============================================================
// GateFlow - TypeScript 类型定义
// ============================================================

// ---------------------
// 用户 / 角色 / 部门
// ---------------------

export interface Role {
  id: number;
  name: string;
  description?: string;
}

export interface Department {
  id: number;
  name: string;
  description?: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  display_name?: string;
  is_active: boolean;
  role: Role;
  department?: Department;
  created_at: string;
  updated_at: string;
}

// ---------------------
// API Key
// ---------------------

export interface APIKey {
  id: number;
  name: string;
  key_prefix: string;
  user: User;
  is_active: boolean;
  rate_limit?: number;
  expires_at?: string;
  created_at: string;
  updated_at: string;
}

// ---------------------
// 网关 - Provider Key / Model
// ---------------------

export interface ProviderKey {
  id: number;
  provider: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  base_url?: string;
  created_at: string;
  updated_at: string;
}

export interface ModelConfig {
  id: number;
  model_name: string;
  provider: string;
  display_name?: string;
  is_enabled: boolean;
  max_tokens?: number;
  temperature?: number;
  provider_key?: ProviderKey;
  created_at: string;
  updated_at: string;
}

// ---------------------
// 聊天 - 会话 / 消息
// ---------------------

export interface Conversation {
  id: number;
  title: string;
  model?: ModelConfig;
  user: User;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  tokens_used?: number;
  created_at: string;
}

// ---------------------
// 审计日志
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

export interface UsageSummary {
  total_requests: number;
  total_tokens: number;
  by_model: {
    model_name: string;
    requests: number;
    tokens: number;
  }[];
  by_user: {
    user_id: number;
    username: string;
    requests: number;
    tokens: number;
  }[];
  period_start: string;
  period_end: string;
}

export interface UsageSummaryItem {
  dimension: string;
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
