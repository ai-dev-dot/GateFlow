import { useEffect, useState } from 'react';
import { Card, Col, Row, Select, DatePicker, Spin, Empty } from 'antd';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';
import { getSummary } from '../api/usage';
import type { UsageSummaryItem } from '../types';

const { RangePicker } = DatePicker;

type Dimension = 'model' | 'department' | 'user' | 'api_key';

const dimensionOptions = [
  { value: 'model', label: '模型' },
  { value: 'department', label: '部门' },
  { value: 'user', label: '用户' },
  { value: 'api_key', label: '客户端' },
];

/** 格式化大数字：1.2M / 3.5K */
function fmtNum(v: number): string {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
  if (v >= 1_000) return (v / 1_000).toFixed(1) + 'K';
  return String(v);
}

export default function Usage() {
  const [dimension, setDimension] = useState<Dimension>('model');
  const [dateRange, setDateRange] = useState<
    [dayjs.Dayjs | null, dayjs.Dayjs | null] | null
  >(null);
  const [items, setItems] = useState<UsageSummaryItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params: { dimension: Dimension; start_date?: string; end_date?: string } = {
        dimension,
      };
      if (dateRange?.[0]) params.start_date = dateRange[0].format('YYYY-MM-DD');
      if (dateRange?.[1]) params.end_date = dateRange[1].format('YYYY-MM-DD');

      const res = await getSummary(params);
      setItems(res.items);
    } catch {
      // 错误已由 axios 拦截器统一处理
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dimension, dateRange]);

  // -------- Bar Chart: 堆叠柱状图（input / output tokens） --------
  const barOption = {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
    },
    legend: { data: ['输入 Tokens', '输出 Tokens'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category' as const,
      data: items.map((i) => i.dimension || '未知'),
      axisLabel: { rotate: items.length > 8 ? 30 : 0 },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: { formatter: (v: number) => fmtNum(v) },
    },
    series: [
      {
        name: '输入 Tokens',
        type: 'bar',
        stack: 'tokens',
        barMaxWidth: 40,
        itemStyle: {
          borderRadius: [0, 0, 0, 0],
          color: '#1890ff',
        },
        data: items.map((i) => i.input_tokens),
      },
      {
        name: '输出 Tokens',
        type: 'bar',
        stack: 'tokens',
        barMaxWidth: 40,
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: '#52c41a',
        },
        data: items.map((i) => i.output_tokens),
      },
    ],
  };

  // -------- Pie Chart: 请求次数占比 --------
  const pieOption = {
    tooltip: { trigger: 'item' as const },
    legend: { orient: 'vertical' as const, left: 'left', top: 'middle' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
        label: { show: false, position: 'center' as const },
        emphasis: {
          label: { show: true, fontSize: 16, fontWeight: 'bold' as const },
        },
        labelLine: { show: false },
        data: items.map((i) => ({
          name: i.dimension || '未知',
          value: i.request_count,
        })),
      },
    ],
  };

  const hasData = items.length > 0;

  return (
    <Spin spinning={loading}>
      {/* 筛选栏 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Select<Dimension>
            value={dimension}
            onChange={setDimension}
            options={dimensionOptions}
            style={{ width: 120 }}
          />
        </Col>
        <Col>
          <RangePicker
            value={dateRange ?? undefined}
            onChange={(dates) =>
              setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)
            }
            allowClear
          />
        </Col>
      </Row>

      {/* 图表 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="Token 用量（输入 / 输出）">
            {hasData ? (
              <ReactECharts option={barOption} style={{ height: 400 }} />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="请求次数占比">
            {hasData ? (
              <ReactECharts option={pieOption} style={{ height: 400 }} />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>
      </Row>
    </Spin>
  );
}
