import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Layout,
  Button,
  Select,
  Input,
  Typography,
  Popconfirm,
  Empty,
  Spin,
  message,
} from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  SendOutlined,
  UserOutlined,
  RobotOutlined,
} from '@ant-design/icons'
import { listModels } from '@/api/gateway'
import {
  listConversations,
  createConversation,
  getMessages,
  sendMessage,
  deleteConversation,
} from '@/api/chat'
import type { ModelConfig, Conversation, Message } from '@/types'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const { Sider, Content } = Layout
const { Text } = Typography

/* ---------- 日期分组辅助 ---------- */

type DateGroup = '今天' | '昨天' | '更早'

function getDateGroup(dateStr: string): DateGroup {
  const d = dayjs(dateStr)
  const now = dayjs()
  if (d.isSame(now, 'day')) return '今天'
  if (d.isSame(now.subtract(1, 'day'), 'day')) return '昨天'
  return '更早'
}

function groupConversations(list: Conversation[]): { label: DateGroup; items: Conversation[] }[] {
  const groups: Record<DateGroup, Conversation[]> = { '今天': [], '昨天': [], '更早': [] }
  for (const c of list) {
    const g = getDateGroup(c.created_at)
    groups[g].push(c)
  }
  return (['今天', '昨天', '更早'] as DateGroup[])
    .filter((label) => groups[label].length > 0)
    .map((label) => ({ label, items: groups[label] }))
}

/* ---------- 组件 ---------- */

export default function Chat() {
  /* ---- state ---- */
  const [models, setModels] = useState<ModelConfig[]>([])
  const [selectedModelId, setSelectedModelId] = useState<string | undefined>()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [loadingConvs, setLoadingConvs] = useState(false)
  const [loadingMsgs, setLoadingMsgs] = useState(false)
  const [sending, setSending] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<any>(null)

  /* ---- 滚动到底部 ---- */
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  /* ---- 加载模型列表 ---- */
  useEffect(() => {
    listModels({ page: 1, page_size: 100 })
      .then((res) => {
        const enabled = res.items.filter((m) => m.is_active)
        setModels(enabled)
        if (enabled.length > 0) setSelectedModelId(enabled[0].id)
      })
      .catch(() => {})
  }, [])

  /* ---- 加载会话列表 ---- */
  const fetchConversations = useCallback(async () => {
    setLoadingConvs(true)
    try {
      const res = await listConversations({ page: 1, page_size: 200 })
      setConversations(res.items)
    } catch {
      // ignore
    } finally {
      setLoadingConvs(false)
    }
  }, [])

  useEffect(() => {
    fetchConversations()
  }, [fetchConversations])

  /* ---- 加载消息 ---- */
  useEffect(() => {
    if (!activeConvId) {
      setMessages([])
      return
    }
    setLoadingMsgs(true)
    getMessages(activeConvId, { page: 1, page_size: 200 })
      .then((res) => setMessages(res.items))
      .catch(() => message.error('加载消息失败'))
      .finally(() => setLoadingMsgs(false))
  }, [activeConvId])

  /* ---- 新消息后滚动 ---- */
  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  /* ---- 新建会话 ---- */
  const handleNewConversation = async () => {
    try {
      const conv = await createConversation({ model_id: selectedModelId })
      setConversations((prev) => [conv, ...prev])
      setActiveConvId(conv.id)
      setInputValue('')
    } catch {
      message.error('创建会话失败')
    }
  }

  /* ---- 删除会话 ---- */
  const handleDeleteConversation = async (id: number) => {
    try {
      await deleteConversation(id)
      setConversations((prev) => prev.filter((c) => c.id !== id))
      if (activeConvId === id) {
        setActiveConvId(null)
        setMessages([])
      }
      message.success('已删除')
    } catch {
      message.error('删除失败')
    }
  }

  /* ---- 发送消息 ---- */
  const handleSend = async () => {
    const text = inputValue.trim()
    if (!text || !activeConvId || sending) return

    setSending(true)
    setInputValue('')

    // 乐观插入用户消息
    const tempUserMsg: Message = {
      id: Date.now(),
      conversation_id: activeConvId,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, tempUserMsg])

    try {
      await sendMessage(activeConvId, { content: text })
      // 重新加载消息以获取完整的用户消息和 AI 回复
      const res = await getMessages(activeConvId, { page: 1, page_size: 200 })
      setMessages(res.items)
    } catch {
      message.error('发送失败')
      // 移除乐观插入的临时消息
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id))
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  /* ---- 键盘发送 ---- */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  /* ---- 分组 ---- */
  const grouped = groupConversations(conversations)

  /* ---- 渲染 ---- */
  return (
    <Layout style={{ height: 'calc(100vh - 64px - 48px)', background: 'transparent' }}>
      {/* ========== 左侧栏 ========== */}
      <Sider
        width={280}
        style={{
          background: '#fff',
          borderRight: '1px solid #f0f0f0',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          borderRadius: '8px 0 0 8px',
        }}
      >
        {/* 顶部操作区 */}
        <div style={{ padding: '16px 12px 8px', borderBottom: '1px solid #f0f0f0' }}>
          {/* 模型选择 */}
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>
              模型
            </Text>
            <Select
              style={{ width: '100%' }}
              placeholder="选择模型"
              value={selectedModelId}
              onChange={setSelectedModelId}
              options={models.map((m) => ({
                value: m.id,
                label: m.model_alias,
              }))}
              size="small"
            />
          </div>
          {/* 新建会话 */}
          <Button
            type="primary"
            icon={<PlusOutlined />}
            block
            onClick={handleNewConversation}
            disabled={!selectedModelId}
          >
            新建对话
          </Button>
        </div>

        {/* 会话列表 */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {loadingConvs ? (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <Spin size="small" />
            </div>
          ) : conversations.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无对话"
              style={{ marginTop: 48 }}
            />
          ) : (
            grouped.map((group) => (
              <div key={group.label}>
                <div
                  style={{
                    padding: '8px 16px 4px',
                    fontSize: 12,
                    color: '#999',
                    fontWeight: 500,
                  }}
                >
                  {group.label}
                </div>
                {group.items.map((conv) => (
                  <div
                    key={conv.id}
                    onClick={() => setActiveConvId(conv.id)}
                    style={{
                      padding: '10px 16px',
                      cursor: 'pointer',
                      background: activeConvId === conv.id ? '#e6f4ff' : 'transparent',
                      borderLeft:
                        activeConvId === conv.id ? '3px solid #1677ff' : '3px solid transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      transition: 'background 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      if (activeConvId !== conv.id) {
                        e.currentTarget.style.background = '#fafafa'
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (activeConvId !== conv.id) {
                        e.currentTarget.style.background = 'transparent'
                      }
                    }}
                  >
                    <Text
                      ellipsis
                      style={{ flex: 1, fontSize: 14, marginRight: 8 }}
                      title={conv.title}
                    >
                      {conv.title || '新对话'}
                    </Text>
                    <Popconfirm
                      title="确定删除此对话？"
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        handleDeleteConversation(conv.id)
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                        style={{ color: '#999', flexShrink: 0 }}
                      />
                    </Popconfirm>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      </Sider>

      {/* ========== 右侧主区域 ========== */}
      <Content
        style={{
          display: 'flex',
          flexDirection: 'column',
          background: '#fff',
          borderRadius: '0 8px 8px 0',
          overflow: 'hidden',
        }}
      >
        {activeConvId ? (
          <>
            {/* 消息列表 */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '24px 16px',
                background: '#f7f7f8',
              }}
            >
              {loadingMsgs ? (
                <div style={{ textAlign: 'center', paddingTop: 100 }}>
                  <Spin />
                </div>
              ) : messages.length === 0 ? (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    color: '#bbb',
                  }}
                >
                  <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
                  <Text type="secondary" style={{ fontSize: 16 }}>
                    发送消息开始对话
                  </Text>
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
                        display: 'flex',
                        alignItems: 'flex-start',
                        maxWidth: '70%',
                        flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                      }}
                    >
                      {/* 头像 */}
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: '50%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                          margin: msg.role === 'user' ? '0 0 0 8px' : '0 8px 0 0',
                          background: msg.role === 'user' ? '#1677ff' : '#f0f0f0',
                          color: msg.role === 'user' ? '#fff' : '#666',
                        }}
                      >
                        {msg.role === 'user' ? (
                          <UserOutlined style={{ fontSize: 16 }} />
                        ) : (
                          <RobotOutlined style={{ fontSize: 16 }} />
                        )}
                      </div>
                      {/* 气泡 */}
                      <div
                        style={{
                          padding: '10px 14px',
                          borderRadius: 12,
                          background: msg.role === 'user' ? '#1677ff' : '#fff',
                          color: msg.role === 'user' ? '#fff' : '#333',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
                          wordBreak: 'break-word',
                          lineHeight: 1.6,
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {msg.content}
                      </div>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* 输入框 */}
            <div
              style={{
                padding: '12px 16px',
                borderTop: '1px solid #f0f0f0',
                background: '#fff',
              }}
            >
              <div style={{ display: 'flex', gap: 8 }}>
                <Input.TextArea
                  ref={inputRef}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="输入消息，Enter 发送，Shift+Enter 换行..."
                  autoSize={{ minRows: 1, maxRows: 4 }}
                  style={{ flex: 1, borderRadius: 8 }}
                  disabled={sending}
                />
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSend}
                  loading={sending}
                  disabled={!inputValue.trim()}
                  style={{ borderRadius: 8, height: 'auto' }}
                >
                  发送
                </Button>
              </div>
            </div>
          </>
        ) : (
          /* 未选中会话时的空状态 */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#bbb',
            }}
          >
            <RobotOutlined style={{ fontSize: 64, marginBottom: 24 }} />
            <Text type="secondary" style={{ fontSize: 18, marginBottom: 8 }}>
              欢迎使用 GateFlow AI 助手
            </Text>
            <Text type="secondary">
              选择一个对话或点击「新建对话」开始
            </Text>
          </div>
        )}
      </Content>
    </Layout>
  )
}
