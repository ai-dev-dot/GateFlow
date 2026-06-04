import { useState, useEffect, useCallback } from 'react';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  Popconfirm,
  Space,
  message,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  listUsers,
  createUser,
  updateUser,
  deleteUser,
  listRoles,
  listDepartments,
} from '@/api/users';
import type { User, Role, Department } from '@/types';

// 角色颜色映射
const roleColorMap: Record<string, string> = {
  admin: 'red',
  user: 'blue',
  viewer: 'green',
};

export default function Users() {
  const [data, setData] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [form] = Form.useForm();

  const fetchData = useCallback(
    async (p = page) => {
      setLoading(true);
      try {
        const res = await listUsers({ page: p, page_size: 20 });
        setData(res.items);
        setTotal(res.total);
      } catch {
        // 错误由拦截器处理
      } finally {
        setLoading(false);
      }
    },
    [page],
  );

  const fetchOptions = useCallback(async () => {
    try {
      const [r, d] = await Promise.all([listRoles(), listDepartments()]);
      setRoles(r);
      setDepartments(d);
    } catch {
      // 错误由拦截器处理
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    fetchOptions();
  }, [fetchOptions]);

  const handleAdd = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleEdit = (record: User) => {
    setEditing(record);
    form.setFieldsValue({
      email: record.email,
      role_id: record.role?.id,
      department_id: record.department?.id,
      is_active: record.is_active,
    });
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteUser(id);
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
        await updateUser(editing.id, {
          email: values.email,
          role: { id: values.role_id } as Role,
          department: values.department_id
            ? ({ id: values.department_id } as Department)
            : undefined,
          is_active: values.is_active,
        });
        message.success('已更新');
      } else {
        await createUser({
          username: values.username,
          password: values.password,
          email: values.email,
          role: { id: values.role_id } as Role,
          department: values.department_id
            ? ({ id: values.department_id } as Department)
            : undefined,
        });
        message.success('已创建');
      }
      setModalOpen(false);
      fetchData();
    } catch {
      // 表单校验失败或 API 错误
    }
  };

  const columns: ColumnsType<User> = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: '角色',
      dataIndex: ['role', 'name'],
      key: 'role',
      render: (_: unknown, record: User) => {
        const name = record.role?.name || '-';
        const color = roleColorMap[name.toLowerCase()] || 'default';
        return <Tag color={color}>{name}</Tag>;
      },
    },
    {
      title: '部门',
      dataIndex: ['department', 'name'],
      key: 'department',
      render: (_: unknown, record: User) => record.department?.name || '-',
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
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: unknown, record: User) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="确定删除此用户？"
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
          添加用户
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
        title={editing ? '编辑用户' : '添加用户'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          {!editing && (
            <>
              <Form.Item
                name="username"
                label="用户名"
                rules={[{ required: true, message: '请输入用户名' }]}
              >
                <Input placeholder="用户名" />
              </Form.Item>
              <Form.Item
                name="password"
                label="密码"
                rules={[{ required: true, message: '请输入密码' }]}
              >
                <Input.Password placeholder="密码" />
              </Form.Item>
            </>
          )}
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input placeholder="邮箱地址" />
          </Form.Item>
          <Form.Item
            name="role_id"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select
              placeholder="选择角色"
              options={roles.map((r) => ({ value: r.id, label: r.name }))}
            />
          </Form.Item>
          <Form.Item name="department_id" label="部门">
            <Select
              placeholder="选择部门"
              allowClear
              options={departments.map((d) => ({
                value: d.id,
                label: d.name,
              }))}
            />
          </Form.Item>
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
      </Modal>
    </div>
  );
}
