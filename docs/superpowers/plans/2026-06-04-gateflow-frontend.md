# 闸机 GateFlow 前端实现计划

> **⚠️ 已废弃：** 2026-06-06 前端已从 React 迁移到 Jinja2 + htmx + Tailwind CSS，`frontend/` 目录已删除。本计划仅作历史参考。详见 `2026-06-06-frontend-refactor.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建闸机 GateFlow 前端管理后台，包含登录、AI 问答（豆包风格）、控制台、网关管理、用户管理、审计日志、用量统计 7 个页面。

**Architecture:** 使用 Vite + React 18 + TypeScript + Ant Design 5 构建单页应用。采用 React Router v6 进行路由管理，Axios 封装 API 调用，Zustand 做轻量状态管理。

**Tech Stack:** Vite, React 18, TypeScript, Ant Design 5, React Router v6, Axios, Zustand, ECharts

> **注：** 设计稿原定使用 Umi 框架，但考虑到 MVP 阶段的开发效率和灵活性，改用 Vite + React Router 方案。Umi 的约定式路由和内置功能在项目规模较大时才有明显优势，MVP 阶段使用更轻量的方案可以更快迭代。

---

## 文件结构总览

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── src/
│   ├── main.tsx                    # 应用入口
│   ├── App.tsx                     # 路由配置
│   ├── vite-env.d.ts
│   ├── api/                        # API 调用封装
│   │   ├── client.ts               # Axios 实例
│   │   ├── auth.ts                 # 认证 API
│   │   ├── users.ts                # 用户管理 API
│   │   ├── apiKeys.ts              # API Key 管理 API
│   │   ├── gateway.ts              # 网关管理 API
│   │   ├── chat.ts                 # 问答对话 API
│   │   ├── audit.ts                # 审计日志 API
│   │   └── usage.ts                # 用量统计 API
│   ├── stores/                     # Zustand 状态管理
│   │   └── auth.ts                 # 认证状态
│   ├── components/                 # 通用组件
│   │   ├── Layout.tsx              # 主布局（侧边栏 + 顶栏）
│   │   └── ProtectedRoute.tsx      # 路由守卫
│   ├── pages/                      # 页面组件
│   │   ├── Login.tsx               # 登录页
│   │   ├── Chat.tsx                # AI 问答页（豆包风格）
│   │   ├── Dashboard.tsx           # 控制台首页
│   │   ├── Gateway.tsx             # 网关管理
│   │   ├── Users.tsx               # 用户管理
│   │   ├── Audit.tsx               # 审计日志
│   │   └── Usage.tsx               # 用量统计
│   └── types/                      # TypeScript 类型定义
│       └── index.ts
└── public/
```

---

## Task 1: 前端项目初始化

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/vite-env.d.ts`

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "gateflow-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "antd": "^5.22.0",
    "@ant-design/icons": "^5.5.0",
    "axios": "^1.7.0",
    "zustand": "^5.0.0",
    "echarts": "^5.5.0",
    "echarts-for-react": "^3.0.2",
    "dayjs": "^1.11.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0"
  }
}
```

- [ ] **Step 2: 创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: 创建 tsconfig.node.json**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: 创建 vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 5: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>闸机 GateFlow</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: 创建 src/vite-env.d.ts**

```typescript
/// <reference types="vite/client" />
```

- [ ] **Step 7: 创建 src/main.tsx**

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ConfigProvider locale={zhCN}>
        <App />
      </ConfigProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
```

- [ ] **Step 8: 创建 src/App.tsx（基础版本）**

```tsx
import { Routes, Route, Navigate } from 'react-router-dom'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/chat" replace />} />
    </Routes>
  )
}

export default App
```

- [ ] **Step 9: 安装依赖并验证**

Run: `cd D:/APP/GateFlow/frontend && npm install`
Run: `cd D:/APP/GateFlow/frontend && npm run dev`
Expected: 看到 Vite 启动信息，访问 http://localhost:3000

- [ ] **Step 10: 提交**

```bash
git add frontend/
git commit -m "feat: 初始化前端项目（Vite + React + TypeScript）"
```

---

## Task 2: API 调用封装和类型定义

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/api/users.ts`
- Create: `frontend/src/api/apiKeys.ts`
- Create: `frontend/src/api/gateway.ts`
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/api/audit.ts`
- Create: `frontend/src/api/usage.ts`

- [ ] **Step 1: 创建 types/index.ts**

```typescript
// frontend/src/types/index.ts

export interface User {
  id: string
  username: string
  email: string
  department_id: string | null
  role_id: string
  is_active: boolean
  created_at: string
  last_login: string | null
}

export interface Role {
  id: string
  name: string
  permissions: string[]
}

export interface Department {
  id: string
  name: string
  parent_id: string | null
}

export interface APIKey {
  id: string
  name: string
  key: string
  permissions: string[]
  rate_limit: number
  expires_at: string | null
  is_active: boolean
  created_at: string
  last_used_at: string | null
}

export interface ProviderKey {
  id: string
  provider: string
  name: string
  remark: string | null
  is_active: boolean
  is_banned: boolean
  ban_reason: string | null
  rpm_limit: number
  tpm_limit: number
  total_requests: number
  total_input_tokens: number
  total_output_tokens: number
  consecutive_errors: number
  cool_down_until: string | null
  created_at: string
  last_used_at: string | null
}

export interface ModelConfig {
  id: string
  model_alias: string
  provider: string
  target_model: string
  target_url: string
  is_active: boolean
  priority: number
  default_temperature: number | null
  default_max_tokens: number | null
  created_at: string
}

export interface Conversation {
  id: string
  model: string
  title: string | null
  created_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tokens: number
  created_at: string
}

export interface AuditLog {
  id: string
  status: string
  timestamp: string
  user_id: string
  username: string
  department: string | null
  model: string
  provider: string | null
  method: string
  path: string
  request_body: string | null
  request_tokens: number
  response_tokens: number
  total_tokens: number
  latency_ms: number | null
  status_code: number | null
  is_stream: boolean
  created_at: string
  completed_at: string | null
}

export interface UsageSummary {
  dimension: string
  data: {
    name: string
    total_requests: number
    input_tokens: number
    output_tokens: number
    total_tokens: number
  }[]
}

export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}
```

- [ ] **Step 2: 创建 api/client.ts**

```typescript
// frontend/src/api/client.ts
import axios from 'axios'
import { message } from 'antd'

const client = axios.create({
  baseURL: '',
  timeout: 30000,
})

// 请求拦截器：添加 Token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：处理错误
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    } else if (error.response?.status === 403) {
      message.error('权限不足')
    } else if (error.response?.data?.detail) {
      message.error(error.response.data.detail)
    }
    return Promise.reject(error)
  }
)

export default client
```

- [ ] **Step 3: 创建 api/auth.ts**

```typescript
// frontend/src/api/auth.ts
import client from './client'
import type { LoginRequest, TokenResponse } from '@/types'

export const authApi = {
  login: (data: LoginRequest) =>
    client.post<TokenResponse>('/api/auth/login', data),

  refreshToken: () =>
    client.post<TokenResponse>('/api/auth/refresh'),

  changePassword: (oldPassword: string, newPassword: string) =>
    client.put('/api/auth/password', {
      old_password: oldPassword,
      new_password: newPassword,
    }),
}
```

- [ ] **Step 4: 创建 api/users.ts**

```typescript
// frontend/src/api/users.ts
import client from './client'
import type { User, Role, Department } from '@/types'

export const usersApi = {
  list: () => client.get<User[]>('/api/users'),

  create: (data: {
    username: string
    email: string
    password: string
    role_id: string
    department_id?: string
  }) => client.post<User>('/api/users', data),

  update: (id: string, data: Partial<User>) =>
    client.put<User>(`/api/users/${id}`, data),

  delete: (id: string) =>
    client.delete(`/api/users/${id}`),

  listRoles: () => client.get<Role[]>('/api/users/roles'),

  listDepartments: () => client.get<Department[]>('/api/users/departments'),

  createDepartment: (data: { name: string; parent_id?: string }) =>
    client.post<Department>('/api/users/departments', data),
}
```

- [ ] **Step 5: 创建 api/apiKeys.ts**

```typescript
// frontend/src/api/apiKeys.ts
import client from './client'
import type { APIKey } from '@/types'

export const apiKeysApi = {
  list: () => client.get<APIKey[]>('/api/api-keys'),

  create: (data: {
    name: string
    permissions?: string[]
    rate_limit?: number
    expires_at?: string
  }) => client.post<APIKey>('/api/api-keys', data),

  update: (id: string, data: Partial<APIKey>) =>
    client.put<APIKey>(`/api/api-keys/${id}`, data),

  delete: (id: string) =>
    client.delete(`/api/api-keys/${id}`),
}
```

- [ ] **Step 6: 创建 api/gateway.ts**

```typescript
// frontend/src/api/gateway.ts
import client from './client'
import type { ModelConfig, ProviderKey } from '@/types'

export const gatewayApi = {
  // 模型配置
  listModels: () => client.get<ModelConfig[]>('/api/gateway/models'),

  createModel: (data: Omit<ModelConfig, 'id' | 'created_at'>) =>
    client.post<ModelConfig>('/api/gateway/models', data),

  updateModel: (id: string, data: Partial<ModelConfig>) =>
    client.put<ModelConfig>(`/api/gateway/models/${id}`, data),

  deleteModel: (id: string) =>
    client.delete(`/api/gateway/models/${id}`),

  // 上游 Key
  listProviderKeys: (provider?: string) =>
    client.get<ProviderKey[]>('/api/gateway/provider-keys', {
      params: provider ? { provider } : undefined,
    }),

  createProviderKey: (data: {
    provider: string
    key: string
    name: string
    remark?: string
    rpm_limit?: number
    tpm_limit?: number
  }) => client.post<ProviderKey>('/api/gateway/provider-keys', data),

  updateProviderKey: (id: string, data: Partial<ProviderKey>) =>
    client.put<ProviderKey>(`/api/gateway/provider-keys/${id}`, data),

  deleteProviderKey: (id: string) =>
    client.delete(`/api/gateway/provider-keys/${id}`),

  resetProviderKey: (id: string) =>
    client.post(`/api/gateway/provider-keys/${id}/reset`),
}
```

- [ ] **Step 7: 创建 api/chat.ts**

```typescript
// frontend/src/api/chat.ts
import client from './client'
import type { Conversation, Message } from '@/types'

export const chatApi = {
  listConversations: () =>
    client.get<Conversation[]>('/api/chat/conversations'),

  createConversation: (model: string) =>
    client.post<Conversation>('/api/chat/conversations', { model }),

  getMessages: (conversationId: string) =>
    client.get<Message[]>(`/api/chat/conversations/${conversationId}/messages`),

  sendMessage: (conversationId: string, content: string) =>
    client.post<Message>(`/api/chat/conversations/${conversationId}/messages`, {
      content,
    }),

  deleteConversation: (conversationId: string) =>
    client.delete(`/api/chat/conversations/${conversationId}`),
}
```

- [ ] **Step 8: 创建 api/audit.ts**

```typescript
// frontend/src/api/audit.ts
import client from './client'
import type { AuditLog } from '@/types'

export const auditApi = {
  listLogs: (params?: {
    user_id?: string
    department?: string
    model?: string
    start_time?: string
    end_time?: string
    page?: number
    page_size?: number
  }) =>
    client.get<{ logs: AuditLog[]; page: number; page_size: number }>(
      '/api/audit/logs',
      { params }
    ),
}
```

- [ ] **Step 9: 创建 api/usage.ts**

```typescript
// frontend/src/api/usage.ts
import client from './client'
import type { UsageSummary } from '@/types'

export const usageApi = {
  getSummary: (params: {
    dimension: 'user' | 'department' | 'model'
    start_date?: string
    end_date?: string
  }) => client.get<UsageSummary>('/api/usage/summary', { params }),
}
```

- [ ] **Step 10: 提交**

```bash
git add frontend/src/
git commit -m "feat: 添加 API 调用封装和 TypeScript 类型定义"
```

---

## Task 3: 认证状态管理和路由守卫

**Files:**
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/components/ProtectedRoute.tsx`

- [ ] **Step 1: 创建 stores/auth.ts**

```typescript
// frontend/src/stores/auth.ts
import { create } from 'zustand'
import { authApi } from '@/api/auth'

interface AuthState {
  token: string | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshToken: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),

  login: async (username: string, password: string) => {
    const { data } = await authApi.login({ username, password })
    localStorage.setItem('token', data.access_token)
    set({ token: data.access_token, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ token: null, isAuthenticated: false })
    window.location.href = '/login'
  },

  refreshToken: async () => {
    try {
      const { data } = await authApi.refreshToken()
      localStorage.setItem('token', data.access_token)
      set({ token: data.access_token })
    } catch {
      localStorage.removeItem('token')
      set({ token: null, isAuthenticated: false })
    }
  },
}))
```

- [ ] **Step 2: 创建 components/ProtectedRoute.tsx**

```tsx
// frontend/src/components/ProtectedRoute.tsx
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/
git commit -m "feat: 添加认证状态管理和路由守卫"
```

---

## Task 4: 登录页面

**Files:**
- Create: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 pages/Login.tsx**

```tsx
// frontend/src/pages/Login.tsx
import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Form, Input, Button, Card, message } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/stores/auth'

export default function Login() {
  const [loading, setLoading] = useState(false)
  const login = useAuthStore((state) => state.login)
  const navigate = useNavigate()
  const location = useLocation()

  const from = (location.state as any)?.from?.pathname || '/chat'

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      await login(values.username, values.password)
      message.success('登录成功')
      navigate(from, { replace: true })
    } catch {
      message.error('用户名或密码错误')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: '#f0f2f5',
    }}>
      <Card title="闸机 GateFlow" style={{ width: 400 }}>
        <Form
          name="login"
          initialValues={{ remember: true }}
          onFinish={onFinish}
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: 更新 App.tsx 添加路由**

```tsx
// frontend/src/App.tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to="/chat" replace />} />
      {/* 后续页面在这里添加 */}
    </Routes>
  )
}

export default App
```

- [ ] **Step 3: 验证登录页面**

Run: `cd D:/APP/GateFlow/frontend && npm run dev`
访问 http://localhost:3000/login，应看到登录页面

- [ ] **Step 4: 提交**

```bash
git add frontend/src/
git commit -m "feat: 实现登录页面"
```

---

## Task 5: 主布局组件

**Files:**
- Create: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 components/Layout.tsx**

```tsx
// frontend/src/components/Layout.tsx
import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu, Avatar, Dropdown } from 'antd'
import {
  MessageOutlined,
  DashboardOutlined,
  ApiOutlined,
  UserOutlined,
  FileTextOutlined,
  BarChartOutlined,
  LogoutOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/stores/auth'

const { Header, Sider, Content } = AntLayout

const menuItems = [
  {
    key: '/chat',
    icon: <MessageOutlined />,
    label: 'AI 问答',
  },
  {
    key: '/dashboard',
    icon: <DashboardOutlined />,
    label: '控制台',
  },
  {
    key: '/gateway',
    icon: <ApiOutlined />,
    label: '网关管理',
  },
  {
    key: '/users',
    icon: <UserOutlined />,
    label: '用户管理',
  },
  {
    key: '/audit',
    icon: <FileTextOutlined />,
    label: '审计日志',
  },
  {
    key: '/usage',
    icon: <BarChartOutlined />,
    label: '用量统计',
  },
]

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const logout = useAuthStore((state) => state.logout)

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: logout,
    },
  ]

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{
          height: 32,
          margin: 16,
          background: 'rgba(255, 255, 255, 0.2)',
          borderRadius: 6,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontWeight: 'bold',
        }}>
          {collapsed ? 'GF' : '闸机 GateFlow'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <AntLayout>
        <Header style={{
          padding: '0 24px',
          background: '#fff',
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
        }}>
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Avatar icon={<UserOutlined />} style={{ cursor: 'pointer' }} />
          </Dropdown>
        </Header>
        <Content style={{ margin: '24px 16px', padding: 24, background: '#fff' }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  )
}
```

- [ ] **Step 2: 更新 App.tsx 使用布局**

```tsx
// frontend/src/App.tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import AppLayout from './components/Layout'
import Login from './pages/Login'
import Chat from './pages/Chat'
import Dashboard from './pages/Dashboard'
import Gateway from './pages/Gateway'
import Users from './pages/Users'
import Audit from './pages/Audit'
import Usage from './pages/Usage'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="chat" element={<Chat />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="gateway" element={<Gateway />} />
        <Route path="users" element={<Users />} />
        <Route path="audit" element={<Audit />} />
        <Route path="usage" element={<Usage />} />
      </Route>
    </Routes>
  )
}

export default App
```

- [ ] **Step 3: 创建占位页面**

创建临时占位页面，避免导入错误：

```tsx
// frontend/src/pages/Chat.tsx
export default function Chat() {
  return <div>AI 问答页面（待实现）</div>
}

// frontend/src/pages/Dashboard.tsx
export default function Dashboard() {
  return <div>控制台首页（待实现）</div>
}

// frontend/src/pages/Gateway.tsx
export default function Gateway() {
  return <div>网关管理（待实现）</div>
}

// frontend/src/pages/Users.tsx
export default function Users() {
  return <div>用户管理（待实现）</div>
}

// frontend/src/pages/Audit.tsx
export default function Audit() {
  return <div>审计日志（待实现）</div>
}

// frontend/src/pages/Usage.tsx
export default function Usage() {
  return <div>用量统计（待实现）</div>
}
```

- [ ] **Step 4: 验证布局**

Run: `cd D:/APP/GateFlow/frontend && npm run dev`
登录后应看到侧边栏布局，点击菜单可切换页面

- [ ] **Step 5: 提交**

```bash
git add frontend/src/
git commit -m "feat: 实现主布局和路由配置"
```

---

## Task 6: AI 问答页面（豆包风格）

**Files:**
- Modify: `frontend/src/pages/Chat.tsx`

- [ ] **Step 1: 实现 Chat.tsx**

```tsx
// frontend/src/pages/Chat.tsx
import { useState, useEffect, useRef } from 'react'
import { Input, Button, List, Select, message, Spin } from 'antd'
import { SendOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { chatApi } from '@/api/chat'
import { gatewayApi } from '@/api/gateway'
import type { Conversation, Message, ModelConfig } from '@/types'

export default function Chat() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConversation, setCurrentConversation] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [models, setModels] = useState<ModelConfig[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 加载模型列表
  useEffect(() => {
    gatewayApi.listModels().then(({ data }) => {
      setModels(data)
      if (data.length > 0) {
        setSelectedModel(data[0].model_alias)
      }
    })
  }, [])

  // 加载对话列表
  useEffect(() => {
    chatApi.listConversations().then(({ data }) => {
      setConversations(data)
    })
  }, [])

  // 加载消息
  useEffect(() => {
    if (currentConversation) {
      chatApi.getMessages(currentConversation).then(({ data }) => {
        setMessages(data)
      })
    }
  }, [currentConversation])

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 创建新对话
  const handleNewConversation = async () => {
    if (!selectedModel) {
      message.warning('请先选择模型')
      return
    }
    const { data } = await chatApi.createConversation(selectedModel)
    setConversations([data, ...conversations])
    setCurrentConversation(data.id)
    setMessages([])
  }

  // 发送消息
  const handleSend = async () => {
    if (!inputValue.trim() || !currentConversation || sending) return

    setSending(true)
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      tokens: 0,
      created_at: new Date().toISOString(),
    }
    setMessages([...messages, userMessage])
    setInputValue('')

    try {
      const { data } = await chatApi.sendMessage(currentConversation, inputValue)
      setMessages((prev) => [...prev, data])
    } catch {
      message.error('发送失败')
    } finally {
      setSending(false)
    }
  }

  // 删除对话
  const handleDeleteConversation = async (id: string) => {
    await chatApi.deleteConversation(id)
    setConversations(conversations.filter((c) => c.id !== id))
    if (currentConversation === id) {
      setCurrentConversation(null)
      setMessages([])
    }
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 160px)' }}>
      {/* 侧边栏 - 对话列表 */}
      <div style={{
        width: 280,
        borderRight: '1px solid #f0f0f0',
        display: 'flex',
        flexDirection: 'column',
      }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
          <Select
            value={selectedModel}
            onChange={setSelectedModel}
            style={{ width: '100%', marginBottom: 8 }}
            placeholder="选择模型"
            options={models.map((m) => ({
              value: m.model_alias,
              label: m.model_alias,
            }))}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleNewConversation}
            block
          >
            新对话
          </Button>
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <List
            dataSource={conversations}
            renderItem={(item) => (
              <List.Item
                style={{
                  padding: '12px 16px',
                  cursor: 'pointer',
                  background: currentConversation === item.id ? '#e6f7ff' : 'transparent',
                }}
                onClick={() => setCurrentConversation(item.id)}
                actions={[
                  <Button
                    type="text"
                    icon={<DeleteOutlined />}
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteConversation(item.id)
                    }}
                  />,
                ]}
              >
                <List.Item.Meta
                  title={item.title || '新对话'}
                  description={item.model}
                />
              </List.Item>
            )}
          />
        </div>
      </div>

      {/* 主对话区域 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* 消息列表 */}
        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin />
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
                    maxWidth: '70%',
                    padding: '12px 16px',
                    borderRadius: 8,
                    background: msg.role === 'user' ? '#1890ff' : '#f5f5f5',
                    color: msg.role === 'user' ? 'white' : 'black',
                  }}
                >
                  {msg.content}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入框 */}
        <div style={{ padding: 16, borderTop: '1px solid #f0f0f0' }}>
          <Input.Search
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onSearch={handleSend}
            enterButton={<SendOutlined />}
            placeholder="输入消息..."
            size="large"
            loading={sending}
            disabled={!currentConversation}
          />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 验证问答页面**

登录后访问 /chat，应能看到：
- 左侧对话列表
- 右侧消息区域
- 可以创建新对话、发送消息

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/Chat.tsx
git commit -m "feat: 实现 AI 问答页面（豆包风格）"
```

---

## Task 7: 控制台首页

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: 实现 Dashboard.tsx**

```tsx
// frontend/src/pages/Dashboard.tsx
import { useState, useEffect } from 'react'
import { Row, Col, Card, Statistic } from 'antd'
import {
  MessageOutlined,
  ApiOutlined,
  UserOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { usageApi } from '@/api/usage'
import type { UsageSummary } from '@/types'

export default function Dashboard() {
  const [modelUsage, setModelUsage] = useState<UsageSummary | null>(null)
  const [departmentUsage, setDepartmentUsage] = useState<UsageSummary | null>(null)

  useEffect(() => {
    // 获取本月数据
    const startDate = new Date()
    startDate.setDate(1)
    const startStr = startDate.toISOString().split('T')[0]

    usageApi.getSummary({
      dimension: 'model',
      start_date: startStr,
    }).then(({ data }) => setModelUsage(data))

    usageApi.getSummary({
      dimension: 'department',
      start_date: startStr,
    }).then(({ data }) => setDepartmentUsage(data))
  }, [])

  // 计算总请求量
  const totalRequests = modelUsage?.data.reduce(
    (sum, item) => sum + item.total_requests, 0
  ) || 0

  const totalTokens = modelUsage?.data.reduce(
    (sum, item) => sum + item.total_tokens, 0
  ) || 0

  // 模型占比饼图配置
  const modelPieOption = {
    title: { text: '模型使用占比', left: 'center' },
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: '50%',
        data: modelUsage?.data.map((item) => ({
          name: item.name,
          value: item.total_tokens,
        })) || [],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
      },
    ],
  }

  // 部门排名柱状图配置
  const departmentBarOption = {
    title: { text: '部门用量排名', left: 'center' },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: departmentUsage?.data.map((item) => item.name) || [],
    },
    yAxis: { type: 'value', name: 'Token 数量' },
    series: [
      {
        type: 'bar',
        data: departmentUsage?.data.map((item) => item.total_tokens) || [],
        itemStyle: { borderRadius: [5, 5, 0, 0] },
      },
    ],
  }

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="本月请求量"
              value={totalRequests}
              prefix={<MessageOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="本月 Token 用量"
              value={totalTokens}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="模型数量"
              value={modelUsage?.data.length || 0}
              prefix={<ApiOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="部门数量"
              value={departmentUsage?.data.length || 0}
              prefix={<UserOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card>
            <ReactECharts option={modelPieOption} style={{ height: 400 }} />
          </Card>
        </Col>
        <Col span={12}>
          <Card>
            <ReactECharts option={departmentBarOption} style={{ height: 400 }} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
```

- [ ] **Step 2: 验证控制台**

登录后访问 /dashboard，应能看到统计卡片和图表

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: 实现控制台首页（统计图表）"
```

---

## Task 8: 网关管理页面

**Files:**
- Modify: `frontend/src/pages/Gateway.tsx`

- [ ] **Step 1: 实现 Gateway.tsx**

```tsx
// frontend/src/pages/Gateway.tsx
import { useState, useEffect } from 'react'
import { Tabs, Table, Button, Modal, Form, Input, InputNumber, Select, Space, Tag, message, Popconfirm } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import { gatewayApi } from '@/api/gateway'
import type { ModelConfig, ProviderKey } from '@/types'

export default function Gateway() {
  const [models, setModels] = useState<ModelConfig[]>([])
  const [providerKeys, setProviderKeys] = useState<ProviderKey[]>([])
  const [modelModalOpen, setModelModalOpen] = useState(false)
  const [keyModalOpen, setKeyModalOpen] = useState(false)
  const [editingModel, setEditingModel] = useState<ModelConfig | null>(null)
  const [editingKey, setEditingKey] = useState<ProviderKey | null>(null)
  const [modelForm] = Form.useForm()
  const [keyForm] = Form.useForm()

  // 加载数据
  const loadModels = () => gatewayApi.listModels().then(({ data }) => setModels(data))
  const loadKeys = () => gatewayApi.listProviderKeys().then(({ data }) => setProviderKeys(data))

  useEffect(() => {
    loadModels()
    loadKeys()
  }, [])

  // 模型配置操作
  const handleSaveModel = async () => {
    const values = await modelForm.validateFields()
    if (editingModel) {
      await gatewayApi.updateModel(editingModel.id, values)
      message.success('更新成功')
    } else {
      await gatewayApi.createModel(values)
      message.success('创建成功')
    }
    setModelModalOpen(false)
    modelForm.resetFields()
    setEditingModel(null)
    loadModels()
  }

  const handleDeleteModel = async (id: string) => {
    await gatewayApi.deleteModel(id)
    message.success('删除成功')
    loadModels()
  }

  // 上游 Key 操作
  const handleSaveKey = async () => {
    const values = await keyForm.validateFields()
    if (editingKey) {
      await gatewayApi.updateProviderKey(editingKey.id, values)
      message.success('更新成功')
    } else {
      await gatewayApi.createProviderKey(values)
      message.success('创建成功')
    }
    setKeyModalOpen(false)
    keyForm.resetFields()
    setEditingKey(null)
    loadKeys()
  }

  const handleDeleteKey = async (id: string) => {
    await gatewayApi.deleteProviderKey(id)
    message.success('删除成功')
    loadKeys()
  }

  const handleResetKey = async (id: string) => {
    await gatewayApi.resetProviderKey(id)
    message.success('重置成功')
    loadKeys()
  }

  // 模型配置表格列
  const modelColumns = [
    { title: '模型别名', dataIndex: 'model_alias', key: 'model_alias' },
    { title: '提供商', dataIndex: 'provider', key: 'provider' },
    { title: '目标模型', dataIndex: 'target_model', key: 'target_model' },
    { title: '目标 URL', dataIndex: 'target_url', key: 'target_url' },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'red'}>{active ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: ModelConfig) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => {
              setEditingModel(record)
              modelForm.setFieldsValue(record)
              setModelModalOpen(true)
            }}
          />
          <Popconfirm title="确认删除？" onConfirm={() => handleDeleteModel(record.id)}>
            <Button icon={<DeleteOutlined />} size="small" danger />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  // 上游 Key 表格列
  const keyColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '提供商', dataIndex: 'provider', key: 'provider' },
    {
      title: '状态',
      key: 'status',
      render: (_: any, record: ProviderKey) => (
        <>
          {record.is_banned && <Tag color="red">已封禁</Tag>}
          {!record.is_active && <Tag color="orange">已禁用</Tag>}
          {record.cool_down_until && new Date(record.cool_down_until) > new Date() && (
            <Tag color="yellow">冷却中</Tag>
          )}
          {record.is_active && !record.is_banned && !record.cool_down_until && (
            <Tag color="green">正常</Tag>
          )}
        </>
      ),
    },
    { title: '总请求', dataIndex: 'total_requests', key: 'total_requests' },
    { title: '连续错误', dataIndex: 'consecutive_errors', key: 'consecutive_errors' },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: ProviderKey) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => {
              setEditingKey(record)
              keyForm.setFieldsValue(record)
              setKeyModalOpen(true)
            }}
          />
          <Button
            icon={<ReloadOutlined />}
            size="small"
            onClick={() => handleResetKey(record.id)}
            title="重置状态"
          />
          <Popconfirm title="确认删除？" onConfirm={() => handleDeleteKey(record.id)}>
            <Button icon={<DeleteOutlined />} size="small" danger />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Tabs
        items={[
          {
            key: 'models',
            label: '模型配置',
            children: (
              <>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setModelModalOpen(true)}
                  style={{ marginBottom: 16 }}
                >
                  添加模型
                </Button>
                <Table columns={modelColumns} dataSource={models} rowKey="id" />
              </>
            ),
          },
          {
            key: 'keys',
            label: '上游 API Key',
            children: (
              <>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setKeyModalOpen(true)}
                  style={{ marginBottom: 16 }}
                >
                  添加 Key
                </Button>
                <Table columns={keyColumns} dataSource={providerKeys} rowKey="id" />
              </>
            ),
          },
        ]}
      />

      {/* 模型配置弹窗 */}
      <Modal
        title={editingModel ? '编辑模型' : '添加模型'}
        open={modelModalOpen}
        onOk={handleSaveModel}
        onCancel={() => {
          setModelModalOpen(false)
          modelForm.resetFields()
          setEditingModel(null)
        }}
      >
        <Form form={modelForm} layout="vertical">
          <Form.Item name="model_alias" label="模型别名" rules={[{ required: true }]}>
            <Input placeholder="如 deepseek-chat" />
          </Form.Item>
          <Form.Item name="provider" label="提供商" rules={[{ required: true }]}>
            <Input placeholder="如 deepseek" />
          </Form.Item>
          <Form.Item name="target_model" label="目标模型" rules={[{ required: true }]}>
            <Input placeholder="上游实际模型名" />
          </Form.Item>
          <Form.Item name="target_url" label="目标 URL" rules={[{ required: true }]}>
            <Input placeholder="https://api.deepseek.com/v1" />
          </Form.Item>
          <Form.Item name="priority" label="优先级">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 上游 Key 弹窗 */}
      <Modal
        title={editingKey ? '编辑 Key' : '添加 Key'}
        open={keyModalOpen}
        onOk={handleSaveKey}
        onCancel={() => {
          setKeyModalOpen(false)
          keyForm.resetFields()
          setEditingKey(null)
        }}
      >
        <Form form={keyForm} layout="vertical">
          <Form.Item name="provider" label="提供商" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'deepseek', label: 'DeepSeek' },
                { value: 'mimo', label: '小米 MiMo' },
              ]}
            />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如 DeepSeek-企业版-1号" />
          </Form.Item>
          {!editingKey && (
            <Form.Item name="key" label="API Key" rules={[{ required: true }]}>
              <Input.Password placeholder="sk-xxx" />
            </Form.Item>
          )}
          <Form.Item name="remark" label="备注">
            <Input.TextArea />
          </Form.Item>
          <Form.Item name="rpm_limit" label="RPM 限制">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="tpm_limit" label="TPM 限制">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
```

- [ ] **Step 2: 验证网关管理页面**

登录后访问 /gateway，应能看到：
- 模型配置 Tab
- 上游 API Key Tab
- 可以增删改查

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/Gateway.tsx
git commit -m "feat: 实现网关管理页面"
```

---

## Task 9: 用户管理页面

**Files:**
- Modify: `frontend/src/pages/Users.tsx`

- [ ] **Step 1: 实现 Users.tsx**

```tsx
// frontend/src/pages/Users.tsx
import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Select, Tag, Space, message, Popconfirm } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { usersApi } from '@/api/users'
import type { User, Role, Department } from '@/types'

export default function Users() {
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [form] = Form.useForm()

  const loadData = async () => {
    const [usersRes, rolesRes, deptsRes] = await Promise.all([
      usersApi.list(),
      usersApi.listRoles(),
      usersApi.listDepartments(),
    ])
    setUsers(usersRes.data)
    setRoles(rolesRes.data)
    setDepartments(deptsRes.data)
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleSave = async () => {
    const values = await form.validateFields()
    if (editingUser) {
      await usersApi.update(editingUser.id, values)
      message.success('更新成功')
    } else {
      await usersApi.create(values)
      message.success('创建成功')
    }
    setModalOpen(false)
    form.resetFields()
    setEditingUser(null)
    loadData()
  }

  const handleDelete = async (id: string) => {
    await usersApi.delete(id)
    message.success('删除成功')
    loadData()
  }

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    {
      title: '角色',
      dataIndex: 'role_id',
      key: 'role_id',
      render: (roleId: string) => {
        const role = roles.find((r) => r.id === roleId)
        const colorMap: Record<string, string> = {
          admin: 'red',
          user: 'blue',
          viewer: 'green',
        }
        return <Tag color={colorMap[role?.name || '']}>{role?.name}</Tag>
      },
    },
    {
      title: '部门',
      dataIndex: 'department_id',
      key: 'department_id',
      render: (deptId: string | null) => {
        if (!deptId) return '-'
        const dept = departments.find((d) => d.id === deptId)
        return dept?.name || '-'
      },
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'red'}>{active ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: User) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => {
              setEditingUser(record)
              form.setFieldsValue(record)
              setModalOpen(true)
            }}
          />
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Button icon={<DeleteOutlined />} size="small" danger />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Button
        type="primary"
        icon={<PlusOutlined />}
        onClick={() => setModalOpen(true)}
        style={{ marginBottom: 16 }}
      >
        添加用户
      </Button>

      <Table columns={columns} dataSource={users} rowKey="id" />

      <Modal
        title={editingUser ? '编辑用户' : '添加用户'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => {
          setModalOpen(false)
          form.resetFields()
          setEditingUser(null)
        }}
      >
        <Form form={form} layout="vertical">
          {!editingUser && (
            <>
              <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name="password" label="密码" rules={[{ required: true }]}>
                <Input.Password />
              </Form.Item>
            </>
          )}
          <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="role_id" label="角色" rules={[{ required: true }]}>
            <Select
              options={roles.map((r) => ({ value: r.id, label: r.name }))}
            />
          </Form.Item>
          <Form.Item name="department_id" label="部门">
            <Select
              allowClear
              options={departments.map((d) => ({ value: d.id, label: d.name }))}
            />
          </Form.Item>
          {editingUser && (
            <Form.Item name="is_active" label="状态">
              <Select
                options={[
                  { value: true, label: '启用' },
                  { value: false, label: '禁用' },
                ]}
              />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  )
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/pages/Users.tsx
git commit -m "feat: 实现用户管理页面"
```

---

## Task 10: 审计日志页面

**Files:**
- Modify: `frontend/src/pages/Audit.tsx`

- [ ] **Step 1: 实现 Audit.tsx**

```tsx
// frontend/src/pages/Audit.tsx
import { useState, useEffect } from 'react'
import { Table, Select, DatePicker, Space, Tag } from 'antd'
import { auditApi } from '@/api/audit'
import { gatewayApi } from '@/api/gateway'
import type { AuditLog, ModelConfig } from '@/types'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

export default function Audit() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [models, setModels] = useState<ModelConfig[]>([])
  const [loading, setLoading] = useState(false)
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 })
  const [filters, setFilters] = useState<{
    model?: string
    dateRange?: [dayjs.Dayjs, dayjs.Dayjs]
  }>({})

  const loadLogs = async (page = 1) => {
    setLoading(true)
    try {
      const params: any = {
        page,
        page_size: pagination.pageSize,
      }
      if (filters.model) params.model = filters.model
      if (filters.dateRange) {
        params.start_time = filters.dateRange[0].toISOString()
        params.end_time = filters.dateRange[1].toISOString()
      }

      const { data } = await auditApi.listLogs(params)
      setLogs(data.logs)
      setPagination((prev) => ({ ...prev, current: page, total: data.logs.length }))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    gatewayApi.listModels().then(({ data }) => setModels(data))
  }, [])

  useEffect(() => {
    loadLogs()
  }, [filters])

  const columns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180,
      render: (t: string) => dayjs(t).format('YYYY-MM-DD HH:mm:ss'),
    },
    { title: '用户', dataIndex: 'username', key: 'username', width: 100 },
    { title: '模型', dataIndex: 'model', key: 'model', width: 120 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (s: string) => (
        <Tag color={s === 'completed' ? 'green' : s === 'failed' ? 'red' : 'blue'}>
          {s}
        </Tag>
      ),
    },
    { title: '输入 Token', dataIndex: 'request_tokens', key: 'request_tokens', width: 100 },
    { title: '输出 Token', dataIndex: 'response_tokens', key: 'response_tokens', width: 100 },
    { title: '耗时(ms)', dataIndex: 'latency_ms', key: 'latency_ms', width: 100 },
    { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 80 },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Select
          placeholder="选择模型"
          allowClear
          style={{ width: 200 }}
          onChange={(value) => setFilters((prev) => ({ ...prev, model: value }))}
          options={models.map((m) => ({ value: m.model_alias, label: m.model_alias }))}
        />
        <RangePicker
          onChange={(dates) =>
            setFilters((prev) => ({
              ...prev,
              dateRange: dates as [dayjs.Dayjs, dayjs.Dayjs] | undefined,
            }))
          }
        />
      </Space>

      <Table
        columns={columns}
        dataSource={logs}
        rowKey="id"
        loading={loading}
        pagination={pagination}
        onChange={(p) => loadLogs(p.current)}
        scroll={{ x: 1000 }}
      />
    </div>
  )
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/pages/Audit.tsx
git commit -m "feat: 实现审计日志页面"
```

---

## Task 11: 用量统计页面

**Files:**
- Modify: `frontend/src/pages/Usage.tsx`

- [ ] **Step 1: 实现 Usage.tsx**

```tsx
// frontend/src/pages/Usage.tsx
import { useState, useEffect } from 'react'
import { Card, Select, DatePicker, Row, Col } from 'antd'
import ReactECharts from 'echarts-for-react'
import { usageApi } from '@/api/usage'
import type { UsageSummary } from '@/types'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

export default function Usage() {
  const [dimension, setDimension] = useState<'user' | 'department' | 'model'>('model')
  const [data, setData] = useState<UsageSummary | null>(null)
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)

  useEffect(() => {
    const params: any = { dimension }
    if (dateRange) {
      params.start_date = dateRange[0].format('YYYY-MM-DD')
      params.end_date = dateRange[1].format('YYYY-MM-DD')
    }
    usageApi.getSummary(params).then((res) => setData(res.data))
  }, [dimension, dateRange])

  // 柱状图配置
  const barOption = {
    title: { text: `${dimension === 'model' ? '模型' : dimension === 'department' ? '部门' : '用户'}用量统计`, left: 'center' },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: data?.data.map((item) => item.name) || [],
      axisLabel: { rotate: 30 },
    },
    yAxis: { type: 'value', name: 'Token 数量' },
    series: [
      {
        name: '输入 Token',
        type: 'bar',
        stack: 'total',
        data: data?.data.map((item) => item.input_tokens) || [],
        itemStyle: { color: '#1890ff' },
      },
      {
        name: '输出 Token',
        type: 'bar',
        stack: 'total',
        data: data?.data.map((item) => item.output_tokens) || [],
        itemStyle: { color: '#52c41a' },
      },
    ],
  }

  // 饼图配置
  const pieOption = {
    title: { text: '请求量占比', left: 'center' },
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: '50%',
        data: data?.data.map((item) => ({
          name: item.name,
          value: item.total_requests,
        })) || [],
      },
    ],
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Select
          value={dimension}
          onChange={setDimension}
          style={{ width: 120, marginRight: 16 }}
          options={[
            { value: 'model', label: '按模型' },
            { value: 'department', label: '按部门' },
            { value: 'user', label: '按用户' },
          ]}
        />
        <RangePicker onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)} />
      </div>

      <Row gutter={16}>
        <Col span={16}>
          <Card>
            <ReactECharts option={barOption} style={{ height: 500 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <ReactECharts option={pieOption} style={{ height: 500 }} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/pages/Usage.tsx
git commit -m "feat: 实现用量统计页面"
```

---

## 实现顺序总结

| Task | 内容 | 预计时间 |
|------|------|---------|
| 1 | 前端项目初始化 | 10 分钟 |
| 2 | API 调用封装和类型定义 | 15 分钟 |
| 3 | 认证状态管理和路由守卫 | 10 分钟 |
| 4 | 登录页面 | 10 分钟 |
| 5 | 主布局组件 | 15 分钟 |
| 6 | AI 问答页面（豆包风格） | 20 分钟 |
| 7 | 控制台首页 | 15 分钟 |
| 8 | 网关管理页面 | 20 分钟 |
| 9 | 用户管理页面 | 15 分钟 |
| 10 | 审计日志页面 | 15 分钟 |
| 11 | 用量统计页面 | 15 分钟 |
| **总计** | | **约 2.5 小时** |
