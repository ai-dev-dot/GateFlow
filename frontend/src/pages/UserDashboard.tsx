import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Spin } from 'antd';
import { SendOutlined, DatabaseOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';
import { getMySummary, getMyTrend } from '../api/usage';
import type { UsageSummaryItem } from '../types';

export default function UserDashboard() {
  const [modelItems, setModelItems] = useState<UsageSummaryItem[]>([]);
  const [trendData, setTrendData] = useState<{ date: string; request_count: number; input_tokens: number; output_tokens: number; total_tokens: number }[]>([]);
  const [totalRequests, setTotalRequests] = useState(0);
  const [totalTokens, setTotalTokens] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const startDate = dayjs().startOf('month').format('YYYY-MM-DD');

    const fetchData = async () => {
      setLoading(true);
      try {
        const [modelRes, trendRes] = await Promise.all([
          getMySummary({ dimension: 'model', start_date: startDate }),
          getMyTrend({ start_date: startDate }),
        ]);

        setModelItems(modelRes.items);
        setTrendData(trendRes.data);

        const reqSum = modelRes.items.reduce((s, i) => s + i.request_count, 0);
        const tokSum = modelRes.items.reduce((s, i) => s + i.total_tokens, 0);
        setTotalRequests(reqSum);
        setTotalTokens(tokSum);
      } catch {
        // 错误已由 axios 拦截器统一处理
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // -------- 折线图：用量趋势 --------
  const trendOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category' as const,
      data: trendData.map((d) => d.date),
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: {
        formatter: (v: number) => {
          if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M';
          if (v >= 1_000) return (v / 1_000).toFixed(0) + 'K';
          return String(v);
        },
      },
    },
    series: [
      {
        name: 'Token 用量',
        type: 'line',
        smooth: true,
        data: trendData.map((d) => d.total_tokens),
        areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#1890ff' },
      },
    ],
  };

  // -------- 饼图：模型用量占比 --------
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

  return (
    <Spin spinning={loading}>
      {/* 统计卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12}>
          <Card>
            <Statistic
              title="本月请求数"
              value={totalRequests}
              prefix={<SendOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card>
            <Statistic
              title="本月 Token 数"
              value={totalTokens}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 图表 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="本月用量趋势">
            {trendData.length > 0 ? (
              <ReactECharts option={trendOption} style={{ height: 320 }} />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                暂无数据
              </div>
            )}
          </Card>
        </Col>
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
      </Row>
    </Spin>
  );
}
