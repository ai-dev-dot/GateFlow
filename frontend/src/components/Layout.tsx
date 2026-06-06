import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Dropdown, Avatar, Space, Modal, Form, Input, message } from 'antd'
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
  LockOutlined,
  DatabaseOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/stores/auth'
import { changePassword } from '@/api/auth'

const { Header, Sider, Content } = Layout

/** 所有菜单项及所需角色，admin 可见全部 */
const allMenuItems = [
  { key: '/chat', icon: <MessageOutlined />, label: 'AI 对话', roles: ['admin', 'user'] },
  { key: '/dashboard', icon: <DashboardOutlined />, label: '全局看板', roles: ['admin'] },
  { key: '/my-usage', icon: <BarChartOutlined />, label: '我的用量', roles: ['user'] },
  { key: '/gateway', icon: <ApiOutlined />, label: '大模型管理', roles: ['admin'] },
  { key: '/users', icon: <UserOutlined />, label: '人员管理', roles: ['admin'] },
  { key: '/audit', icon: <AuditOutlined />, label: 'LLM 调用日志', roles: ['admin'] },
  { key: '/usage', icon: <BarChartOutlined />, label: '使用统计', roles: ['admin'] },
  { key: '/api-keys', icon: <KeyOutlined />, label: 'API Key', roles: ['admin'] },
  { key: '/backup', icon: <DatabaseOutlined />, label: '数据库备份', roles: ['admin'] },
]

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [passwordLoading, setPasswordLoading] = useState(false)
  const [passwordForm] = Form.useForm()
  const navigate = useNavigate()
  const location = useLocation()
  const logout = useAuthStore((state) => state.logout)
  const user = useAuthStore((state) => state.user)

  const role = user?.role || 'user'
  const menuItems = allMenuItems
    .filter((item) => item.roles.includes(role))
    .map(({ roles: _, ...item }) => item)

  const userMenuItems = [
    { key: 'password', icon: <LockOutlined />, label: '修改密码' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
  ]

  const onUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') {
      logout()
    } else if (key === 'password') {
      passwordForm.resetFields()
      setPasswordModalOpen(true)
    }
  }

  const handlePasswordChange = async () => {
    try {
      const values = await passwordForm.validateFields()
      setPasswordLoading(true)
      await changePassword(values.oldPassword, values.newPassword)
      message.success('密码修改成功')
      setPasswordModalOpen(false)
    } catch {
      // 错误由拦截器处理
    } finally {
      setPasswordLoading(false)
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

      <Modal
        title="修改密码"
        open={passwordModalOpen}
        onOk={handlePasswordChange}
        onCancel={() => setPasswordModalOpen(false)}
        confirmLoading={passwordLoading}
        destroyOnClose
      >
        <Form form={passwordForm} layout="vertical" preserve={false}>
          <Form.Item
            name="oldPassword"
            label="旧密码"
            rules={[{ required: true, message: '请输入旧密码' }]}
          >
            <Input.Password placeholder="请输入旧密码" />
          </Form.Item>
          <Form.Item
            name="newPassword"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少 6 个字符' },
            ]}
          >
            <Input.Password placeholder="请输入新密码" />
          </Form.Item>
          <Form.Item
            name="confirmPassword"
            label="确认新密码"
            dependencies={['newPassword']}
            rules={[
              { required: true, message: '请确认新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('newPassword') === value) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password placeholder="请再次输入新密码" />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  )
}
