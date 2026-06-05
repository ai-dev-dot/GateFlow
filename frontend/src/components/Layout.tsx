import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Dropdown, Avatar, Space } from 'antd'
import {
  MessageOutlined,
  DashboardOutlined,
  ApiOutlined,
  UserOutlined,
  AuditOutlined,
  BarChartOutlined,
  KeyOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/stores/auth'

const { Header, Sider, Content } = Layout

/** 所有菜单项及所需角色，admin 可见全部 */
const allMenuItems = [
  { key: '/chat', icon: <MessageOutlined />, label: 'AI 对话', roles: ['admin', 'user'] },
  { key: '/dashboard', icon: <DashboardOutlined />, label: '全局看板', roles: ['admin'] },
  { key: '/my-usage', icon: <BarChartOutlined />, label: '我的用量', roles: ['user'] },
  { key: '/gateway', icon: <ApiOutlined />, label: '闸机管理', roles: ['admin'] },
  { key: '/users', icon: <UserOutlined />, label: '人员管理', roles: ['admin'] },
  { key: '/audit', icon: <AuditOutlined />, label: '审批中心', roles: ['admin'] },
  { key: '/usage', icon: <BarChartOutlined />, label: '使用统计', roles: ['admin'] },
  { key: '/api-keys', icon: <KeyOutlined />, label: 'API Key', roles: ['admin'] },
]

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const logout = useAuthStore((state) => state.logout)
  const user = useAuthStore((state) => state.user)

  const role = user?.role || 'user'
  const menuItems = allMenuItems
    .filter((item) => item.roles.includes(role))
    .map(({ roles: _, ...item }) => item)

  const userMenuItems = [
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
  ]

  const onUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') {
      logout()
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        theme="dark"
        width={220}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: collapsed ? 16 : 20,
            fontWeight: 'bold',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
          }}
        >
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
      <Layout>
        <Header
          style={{
            padding: '0 24px',
            background: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span
            style={{ fontSize: 20, cursor: 'pointer' }}
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </span>
          <Dropdown menu={{ items: userMenuItems, onClick: onUserMenuClick }} placement="bottomRight">
            <Space style={{ cursor: 'pointer' }}>
              <Avatar icon={<UserOutlined />} />
              <span>{user?.username || '未登录'}</span>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, padding: 24, background: '#fff', borderRadius: 8, minHeight: 280 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
