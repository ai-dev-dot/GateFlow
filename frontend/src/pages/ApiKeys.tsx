import { useState, useEffect, useCallback } from 'react';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Tag,
  Popconfirm,
  Space,
  message,
  Tooltip,
  DatePicker,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CopyOutlined,
  KeyOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { listAPIKeys, createAPIKey, updateAPIKey, deleteAPIKey } from '@/api/apiKeys';
import type { APIKey } from '@/types';

/** 可选权限列表 */
const permissionOptions = [
  { value: 'chat', label: '对话' },
  { value: 'models', label: '模型' },
  { value: 'completions', label: '补全' },
];

export default function ApiKeys() {
  const [data, setData] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<APIKey | null>(null);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listAPIKeys();
      setData(res);
    } catch {
      // 错误由拦截器处理
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAdd = () => {
    setEditing(null);
    form.resetFields();
    setNewKey(null);
    setModalOpen(true);
  };

  const handleEdit = (record: APIKey) => {
    setEditing(record);
    setNewKey(null);
    setModalOpen(true);
  };

  // Modal 打开动画完成后设置表单值
  const handleAfterOpenChange = (open: boolean) => {
    if (open && editing) {
      form.setFieldsValue({
        name: editing.name,
        permissions: editing.permissions,
        rate_limit: editing.rate_limit,
        is_active: editing.is_active,
      });
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteAPIKey(id);
      message.success('已删除');
      fetchData();
    } catch {
      // 错误由拦截器处理
    }
  };

  const handleCopyKey = async (key: string) => {
    try {
      await navigator.clipboard.writeText(key);
      message.success('已复制到剪贴板');
    } catch {
      message.error('复制失败，请手动复制');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await updateAPIKey(editing.id, {
          name: values.name,
          permissions: values.permissions,
          rate_limit: values.rate_limit,
          is_active: values.is_active,
        });
        message.success('已更新');
      } else {
        const res = await createAPIKey({
          name: values.name,
          permissions: values.permissions,
          rate_limit: values.rate_limit,
          expires_at: values.expires_at
            ? values.expires_at.toISOString()
            : undefined,
        });
        // 创建成功后显示完整 key
        setNewKey(res.key);
        message.success('API Key 已创建，请立即复制保存，关闭后无法再次查看完整 Key');
      }
      fetchData();
      if (editing) {
        setModalOpen(false);
      }
    } catch {
      // 表单校验失败或 API 错误
    }
  };

  const columns: ColumnsType<APIKey> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: 'Key 前缀',
      key: 'key_prefix',
      width: 200,
      render: (_: unknown, record: APIKey) => (
        <Space>
          <Tag icon={<KeyOutlined />} color="blue">
            {record.key.substring(0, 12)}...
          </Tag>
          <Tooltip title="复制完整 Key">
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={() => handleCopyKey(record.key)}
            />
          </Tooltip>
        </Space>
      ),
    },
    {
      title: '权限',
      dataIndex: 'permissions',
      key: 'permissions',
      render: (val: string[] | undefined) =>
        val && val.length > 0
          ? val.map((p) => (
              <Tag key={p} color="purple">
                {permissionOptions.find((o) => o.value === p)?.label || p}
              </Tag>
            ))
          : '-',
    },
    {
      title: '速率限制',
      dataIndex: 'rate_limit',
      key: 'rate_limit',
      width: 120,
      render: (val: number) => `${val} / min`,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (val: boolean) =>
        val ? (
          <Tag color="green">启用</Tag>
        ) : (
          <Tag color="default">禁用</Tag>
        ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (val: string) => (val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '最后使用',
      dataIndex: 'last_used_at',
      key: 'last_used_at',
      width: 170,
      render: (val: string | undefined) =>
        val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: unknown, record: APIKey) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="确定删除此 API Key？"
            description="删除后使用此 Key 的应用将无法访问。"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24, background: '#fff', borderRadius: 8 }}>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          创建 API Key
        </Button>
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        pagination={{
          current: page,
          pageSize: 20,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => setPage(p),
        }}
      />

      <Modal
        title={editing ? '编辑 API Key' : '创建 API Key'}
        open={modalOpen}
        onOk={newKey ? undefined : handleSubmit}
        onCancel={() => {
          setModalOpen(false);
          setNewKey(null);
        }}
        destroyOnClose
        afterOpenChange={handleAfterOpenChange}
        footer={
          newKey
            ? [
                <Button
                  key="close"
                  type="primary"
                  onClick={() => {
                    setModalOpen(false);
                    setNewKey(null);
                  }}
                >
                  我已保存，关闭
                </Button>,
              ]
            : undefined
        }
      >
        {newKey ? (
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <p style={{ marginBottom: 16, color: '#faad14' }}>
              请立即复制保存此 Key，关闭后无法再次查看完整内容！
            </p>
            <Tag
              color="blue"
              style={{ fontSize: 14, padding: '8px 16px', marginBottom: 16 }}
            >
              {newKey}
            </Tag>
            <div>
              <Button
                type="primary"
                icon={<CopyOutlined />}
                onClick={() => handleCopyKey(newKey)}
              >
                复制 Key
              </Button>
            </div>
          </div>
        ) : (
          <Form form={form} layout="vertical" preserve={false}>
            <Form.Item
              name="name"
              label="名称"
              rules={[{ required: true, message: '请输入名称' }]}
            >
              <Input placeholder="例如：Dify 集成、Cursor 插件" />
            </Form.Item>
            <Form.Item name="permissions" label="权限">
              <Select
                mode="multiple"
                placeholder="选择权限（可选，留空表示全部权限）"
                allowClear
                options={permissionOptions}
              />
            </Form.Item>
            <Form.Item
              name="rate_limit"
              label="速率限制（次/分钟）"
              initialValue={60}
            >
              <InputNumber min={1} max={10000} style={{ width: '100%' }} />
            </Form.Item>
            {!editing && (
              <Form.Item name="expires_at" label="过期时间">
                <DatePicker
                  showTime
                  style={{ width: '100%' }}
                  placeholder="选择过期时间（可选）"
                />
              </Form.Item>
            )}
            {editing && (
              <Form.Item
                name="is_active"
                label="状态"
                valuePropName="checked"
              >
                <Select
                  options={[
                    { value: true, label: '启用' },
                    { value: false, label: '禁用' },
                  ]}
                />
              </Form.Item>
            )}
          </Form>
        )}
      </Modal>
    </div>
  );
}
