import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Spin } from 'antd';
import {
  SendOutlined,
  DatabaseOutlined,
  AppstoreOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';
import { getSummary } from '../api/usage';
import { listModels } from '../api/gateway';
import { listDepartments } from '../api/users';
import type { UsageSummaryItem } from '../types';

export default function Dashboard() {
  const [modelItems, setModelItems] = useState<UsageSummaryItem[]>([]);
  const [deptItems, setDeptItems] = useState<UsageSummaryItem[]>([]);
  const [totalRequests, setTotalRequests] = useState(0);
  const [totalTokens, setTotalTokens] = useState(0);
  const [modelCount, setModelCount] = useState(0);
  const [deptCount, setDeptCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const startDate = dayjs().startOf('month').format('YYYY-MM-DD');

    const fetchData = async () => {
      setLoading(true);
      try {
        const [modelRes, deptRes, models, depts] = await Promise.all([
          getSummary({ dimension: 'model', start_date: startDate }),
          getSummary({ dimension: 'department', start_date: startDate }),
          listModels(),
          listDepartments(),
        ]);

        setModelItems(modelRes.items);
        setDeptItems(deptRes.items);

        // 从 model 维度汇总总请求数和总 token 数
        const reqSum = modelRes.items.reduce((s, i) => s + i.request_count, 0);
        const tokSum = modelRes.items.reduce((s, i) => s + i.total_tokens, 0);
        setTotalRequests(reqSum);
        setTotalTokens(tokSum);

        setModelCount(models.length);
        setDeptCount(depts.length);
      } catch {
        // 错误已由 axios 拦截器统一处理
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // -------- Pie Chart: 模型用量占比 --------
  const pieOption = {
    tooltip: { trigger: 'item' as const },
    legend: { orient: 'vertical' as const, left: 'left', top: 'middle' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
        label: { show: false, position: 'center' },
        emphasis: {
          label: { show: true, fontSize: 16, fontWeight: 'bold' as const },
        },
        labelLine: { show: false },
        data: modelItems.map((item) => ({
          name: item.dimension,
          value: item.total_tokens,
        })),
      },
    ],
  };

  // -------- Bar Chart: 部门用量排名 --------
  const sortedDepts = [...deptItems].sort(
    (a, b) => a.total_tokens - b.total_tokens,
  );

  const barOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'value' as const,
      axisLabel: {
        formatter: (v: number) => {
          if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
          if (v >= 1_000) return (v / 1_000).toFixed(0) + 'K';
          return String(v);
        },
      },
    },
    yAxis: {
      type: 'category' as const,
      data: sortedDepts.map((d) => d.dimension || '未知'),
    },
    series: [
      {
        type: 'bar',
        data: sortedDepts.map((d) => d.total_tokens),
        barMaxWidth: 32,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 1, y2: 0,
            colorStops: [
              { offset: 0, color: '#91d5ff' },
              { offset: 1, color: '#1890ff' },
            ],
          },
        },
      },
    ],
  };

  // -------- Render --------
  return (
    <Spin spinning={loading}>
      {/* 统计卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="本月请求数"
              value={totalRequests}
              prefix={<SendOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="本月 Token 数"
              value={totalTokens}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="模型数量"
              value={modelCount}
              prefix={<AppstoreOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="部门数量"
              value={deptCount}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 图表 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="模型用量占比">
            {modelItems.length > 0 ? (
              <ReactECharts option={pieOption} style={{ height: 320 }} />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                暂无数据
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="部门用量排名">
            {deptItems.length > 0 ? (
              <ReactECharts option={barOption} style={{ height: 320 }} />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                暂无数据
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </Spin>
  );
}
