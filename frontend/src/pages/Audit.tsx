import { useState, useEffect, useCallback } from 'react';
import { Table, Select, DatePicker, Tag, Space, Button } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { listLogs } from '@/api/audit';
import { listModels } from '@/api/gateway';
import type { AuditLog, ModelConfig } from '@/types';

const { RangePicker } = DatePicker;

const statusColorMap: Record<string, string> = {
  success: 'green',
  error: 'red',
  timeout: 'orange',
  rate_limited: 'gold',
};

const statusCodeColorMap: Record<number, string> = {
  200: 'green',
  201: 'green',
  400: 'orange',
  401: 'red',
  403: 'red',
  404: 'orange',
  429: 'gold',
  500: 'red',
  502: 'red',
  503: 'red',
};

export default function Audit() {
  const [data, setData] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [models, setModels] = useState<ModelConfig[]>([]);

  // 筛选条件
  const [selectedModel, setSelectedModel] = useState<string | undefined>();
  const [dateRange, setDateRange] = useState<
    [dayjs.Dayjs | null, dayjs.Dayjs | null] | null
  >(null);

  const fetchData = useCallback(
    async (p = page, ps = pageSize) => {
      setLoading(true);
      try {
        const res = await listLogs({
          page: p,
          page_size: ps,
          model: selectedModel,
          start_date: dateRange?.[0]?.format('YYYY-MM-DD') || undefined,
          end_date: dateRange?.[1]?.format('YYYY-MM-DD') || undefined,
        });
        setData(res.items);
        setTotal(res.total);
      } catch {
        // 错误由拦截器处理
      } finally {
        setLoading(false);
      }
    },
    [page, pageSize, selectedModel, dateRange],
  );

  const fetchModels = useCallback(async () => {
    try {
      const res = await listModels({ page_size: 999 });
      setModels(res.items);
    } catch {
      // 错误由拦截器处理
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleReset = () => {
    setSelectedModel(undefined);
    setDateRange(null);
    setPage(1);
  };

  const handleFilter = () => {
    setPage(1);
  };

  const columns: ColumnsType<AuditLog> = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (val: string) =>
        val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '用户',
      dataIndex: ['user', 'username'],
      key: 'username',
      width: 120,
      render: (_: unknown, record: AuditLog) => record.user?.username || '-',
    },
    {
      title: '模型',
      dataIndex: 'model',
      key: 'model',
      width: 160,
      render: (val: string) => val || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (val: string) => {
        if (!val) return '-';
        const color = statusColorMap[val.toLowerCase()] || 'default';
        return <Tag color={color}>{val}</Tag>;
      },
    },
    {
      title: '请求 Tokens',
      dataIndex: 'request_tokens',
      key: 'request_tokens',
      width: 110,
      align: 'right',
      render: (val: number) =>
        val != null ? val.toLocaleString() : '-',
    },
    {
      title: '响应 Tokens',
      dataIndex: 'response_tokens',
      key: 'response_tokens',
      width: 110,
      align: 'right',
      render: (val: number) =>
        val != null ? val.toLocaleString() : '-',
    },
    {
      title: '延迟 (ms)',
      dataIndex: 'latency_ms',
      key: 'latency_ms',
      width: 100,
      align: 'right',
      render: (val: number) =>
        val != null ? val.toLocaleString() : '-',
    },
    {
      title: '状态码',
      dataIndex: 'status_code',
      key: 'status_code',
      width: 90,
      align: 'center',
      render: (val: number) => {
        if (val == null) return '-';
        const color = statusCodeColorMap[val] || 'default';
        return <Tag color={color}>{val}</Tag>;
      },
    },
  ];

  return (
    <div style={{ padding: 24, background: '#fff', borderRadius: 8 }}>
      {/* 筛选栏 */}
      <div
        style={{
          marginBottom: 16,
          display: 'flex',
          gap: 12,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        <Select
          allowClear
          placeholder="选择模型"
          style={{ width: 200 }}
          value={selectedModel}
          onChange={(val) => {
            setSelectedModel(val);
            setPage(1);
          }}
          options={models.map((m) => ({
            value: m.model_alias,
            label: m.model_alias,
          }))}
        />
        <RangePicker
          value={dateRange as [dayjs.Dayjs, dayjs.Dayjs] | null}
          onChange={(dates) => {
            setDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null);
            setPage(1);
          }}
          placeholder={['开始日期', '结束日期']}
        />
        <Space>
          <Button type="primary" onClick={handleFilter}>
            查询
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重置
          </Button>
        </Space>
      </div>

      {/* 日志表格 */}
      <Table
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        scroll={{ x: 960 }}
        pagination={{
          current: page,
          total,
          pageSize,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />
    </div>
  );
}
