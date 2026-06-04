import { useState, useEffect, useCallback } from 'react';
import {
  Tabs,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  Tag,
  Popconfirm,
  Space,
  message,
  InputNumber,
} from 'antd';
import type { TabsProps } from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  listModels,
  createModel,
  updateModel,
  deleteModel,
  listProviderKeys,
  createProviderKey,
  updateProviderKey,
  deleteProviderKey,
  resetProviderKey,
} from '@/api/gateway';
import type { ModelConfig, ProviderKey } from '@/types';

/* ==================== Model Config Tab ==================== */

function ModelConfigTab() {
  const [data, setData] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ModelConfig | null>(null);
  const [form] = Form.useForm();

  const fetchData = useCallback(async (p = page) => {
    setLoading(true);
    try {
      const res = await listModels({ page: p, page_size: 20 });
      setData(res.items);
      setTotal(res.total);
    } catch {
      // 错误由拦截器处理
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAdd = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleEdit = (record: ModelConfig) => {
    setEditing(record);
    form.setFieldsValue({
      display_name: record.display_name,
      provider: record.provider,
      model_name: record.model_name,
      is_enabled: record.is_enabled,
      max_tokens: record.max_tokens,
      temperature: record.temperature,
    });
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteModel(id);
      message.success('已删除');
      fetchData();
    } catch {
      // 错误由拦截器处理
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await updateModel(editing.id, values);
        message.success('已更新');
      } else {
        await createModel(values);
        message.success('已创建');
      }
      setModalOpen(false);
      fetchData();
    } catch {
      // 表单校验失败或 API 错误
    }
  };

  const columns: ColumnsType<ModelConfig> = [
    {
      title: '模型别名',
      dataIndex: 'display_name',
      key: 'display_name',
      render: (val: string) => val || '-',
    },
    {
      title: '供应商',
      dataIndex: 'provider',
      key: 'provider',
    },
    {
      title: '目标模型',
      dataIndex: 'model_name',
      key: 'model_name',
    },
    {
      title: '状态',
      dataIndex: 'is_enabled',
      key: 'is_enabled',
      width: 80,
      render: (val: boolean) =>
        val ? <Tag color="green">启用</Tag> : <Tag color="default">禁用</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: unknown, record: ModelConfig) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="确定删除此模型配置？"
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
    <>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加模型
        </Button>
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => setPage(p),
        }}
      />

      <Modal
        title={editing ? '编辑模型' : '添加模型'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item
            name="display_name"
            label="模型别名"
          >
            <Input placeholder="可选，用于前端展示" />
          </Form.Item>
          <Form.Item
            name="provider"
            label="供应商"
            rules={[{ required: true, message: '请输入供应商' }]}
          >
            <Input placeholder="例如 openai、anthropic" />
          </Form.Item>
          <Form.Item
            name="model_name"
            label="目标模型"
            rules={[{ required: true, message: '请输入目标模型名称' }]}
          >
            <Input placeholder="例如 gpt-4o、claude-3-sonnet" />
          </Form.Item>
          <Form.Item
            name="max_tokens"
            label="最大 Token 数"
          >
            <InputNumber min={1} style={{ width: '100%' }} placeholder="可选" />
          </Form.Item>
          <Form.Item
            name="temperature"
            label="Temperature"
          >
            <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} placeholder="可选" />
          </Form.Item>
          <Form.Item
            name="is_enabled"
            label="状态"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

/* ==================== Provider Key Tab ==================== */

function ProviderKeyTab() {
  const [data, setData] = useState<ProviderKey[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ProviderKey | null>(null);
  const [resetModalOpen, setResetModalOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState<ProviderKey | null>(null);
  const [form] = Form.useForm();
  const [resetForm] = Form.useForm();

  const fetchData = useCallback(async (p = page) => {
    setLoading(true);
    try {
      const res = await listProviderKeys({ page: p, page_size: 20 });
      setData(res.items);
      setTotal(res.total);
    } catch {
      // 错误由拦截器处理
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAdd = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleEdit = (record: ProviderKey) => {
    setEditing(record);
    form.setFieldsValue({
      name: record.name,
      is_active: record.is_active,
      base_url: record.base_url,
    });
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteProviderKey(id);
      message.success('已删除');
      fetchData();
    } catch {
      // 错误由拦截器处理
    }
  };

  const handleReset = (record: ProviderKey) => {
    setResetTarget(record);
    resetForm.resetFields();
    setResetModalOpen(true);
  };

  const handleResetSubmit = async () => {
    try {
      const values = await resetForm.validateFields();
      if (!resetTarget) return;
      await resetProviderKey(resetTarget.id, { api_key: values.api_key });
      message.success('已重置');
      setResetModalOpen(false);
      fetchData();
    } catch {
      // 表单校验失败或 API 错误
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await updateProviderKey(editing.id, {
          name: values.name,
          is_active: values.is_active,
          base_url: values.base_url,
        });
        message.success('已更新');
      } else {
        await createProviderKey({
          provider: values.provider,
          name: values.name,
          api_key: values.api_key,
          base_url: values.base_url,
        });
        message.success('已创建');
      }
      setModalOpen(false);
      fetchData();
    } catch {
      // 表单校验失败或 API 错误
    }
  };

  const columns: ColumnsType<ProviderKey> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '供应商',
      dataIndex: 'provider',
      key: 'provider',
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (val: boolean) =>
        val ? <Tag color="green">正常</Tag> : <Tag color="red">禁用</Tag>,
    },
    {
      title: '密钥前缀',
      dataIndex: 'key_prefix',
      key: 'key_prefix',
      render: (val: string) => val || '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: unknown, record: ProviderKey) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="确定重置此密钥？将清除错误计数并解除封禁。"
            onConfirm={() => handleReset(record)}
            okText="重置"
            cancelText="取消"
          >
            <Button type="link" size="small" icon={<ReloadOutlined />} />
          </Popconfirm>
          <Popconfirm
            title="确定删除此密钥？"
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
    <>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加密钥
        </Button>
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => setPage(p),
        }}
      />

      {/* 添加/编辑 Modal */}
      <Modal
        title={editing ? '编辑密钥' : '添加密钥'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          {!editing && (
            <Form.Item
              name="provider"
              label="供应商"
              rules={[{ required: true, message: '请输入供应商' }]}
            >
              <Select
                placeholder="选择供应商"
                options={[
                  { value: 'openai', label: 'OpenAI' },
                  { value: 'anthropic', label: 'Anthropic' },
                  { value: 'deepseek', label: 'DeepSeek' },
                  { value: 'other', label: '其他' },
                ]}
              />
            </Form.Item>
          )}
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="密钥名称" />
          </Form.Item>
          {!editing && (
            <Form.Item
              name="api_key"
              label="API Key"
              rules={[{ required: true, message: '请输入 API Key' }]}
            >
              <Input.Password placeholder="sk-..." />
            </Form.Item>
          )}
          <Form.Item name="base_url" label="Base URL">
            <Input placeholder="可选，自定义 API 地址" />
          </Form.Item>
          {editing && (
            <Form.Item
              name="is_active"
              label="状态"
              valuePropName="checked"
            >
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* 重置 Modal */}
      <Modal
        title="重置密钥"
        open={resetModalOpen}
        onOk={handleResetSubmit}
        onCancel={() => setResetModalOpen(false)}
        destroyOnClose
        okText="确认重置"
        cancelText="取消"
      >
        <p>
          重置将清除错误计数并解除封禁状态。请输入新的 API Key：
        </p>
        <Form form={resetForm} layout="vertical" preserve={false}>
          <Form.Item
            name="api_key"
            label="新 API Key"
            rules={[{ required: true, message: '请输入新的 API Key' }]}
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

/* ==================== Main Component ==================== */

export default function Gateway() {
  const tabItems: TabsProps['items'] = [
    {
      key: 'models',
      label: '模型配置',
      children: <ModelConfigTab />,
    },
    {
      key: 'provider-keys',
      label: 'Provider API Key',
      children: <ProviderKeyTab />,
    },
  ];

  return (
    <div style={{ padding: 24, background: '#fff', borderRadius: 8 }}>
      <Tabs defaultActiveKey="models" items={tabItems} />
    </div>
  );
}
