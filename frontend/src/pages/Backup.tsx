/**
 * 数据库备份管理页 (admin only)
 *
 * 三个段：
 *  1. 备份设置 — 备份目录 + 是否包含 LLM 调用日志
 *  2. 立即备份 — Popconfirm 包裹，loading 态可见，结果用 Statistic 行展示
 *  3. 历史备份 — 列出 backup_dir 下的 .sql 文件
 *
 * 后端 PG-only：当前 SQLite 环境 /run 端点会返回 501，这里捕获并展示 detail。
 */

import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Empty,
  Form,
  Input,
  Popconfirm,
  Row,
  Space,
  Statistic,
  Table,
  Tooltip,
  message,
} from 'antd';
import {
  CloudDownloadOutlined,
  DatabaseOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';

import { getConfig, listBackups, runBackup, updateConfig } from '@/api/backup';
import type { BackupFileInfo, BackupResult, SystemConfig } from '@/types';

const formatBytes = (b: number): string => {
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
};

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
};

export default function Backup() {
  const [form] = Form.useForm<SystemConfig>();
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [history, setHistory] = useState<BackupFileInfo[]>([]);
  const [result, setResult] = useState<BackupResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [cfg, hist] = await Promise.all([getConfig(), listBackups()]);
      setConfig(cfg);
      form.setFieldsValue(cfg);
      setHistory(hist);
    } catch {
      // 错误由拦截器处理
    }
  }, [form]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const updated = await updateConfig(values);
      setConfig(updated);
      message.success('设置已保存');
    } catch {
      // 错误由拦截器处理
    } finally {
      setSaving(false);
    }
  };

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await runBackup();
      setResult(r);
      message.success(`备份完成: ${r.filename}`);
      await loadAll();
    } catch (e: unknown) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        '备份失败';
      setError(detail);
    } finally {
      setRunning(false);
    }
  };

  const dirSet = !!config?.backup_dir?.trim();
  const runButton = (
    <Popconfirm
      title="确认立即备份？"
      description="根据数据库大小，可能需要数十秒到数分钟。"
      onConfirm={handleRun}
      okText="开始备份"
      cancelText="取消"
      disabled={!dirSet || running}
    >
      <Tooltip title={!dirSet ? '请先设置备份目录' : ''}>
        <Button
          type="primary"
          size="large"
          icon={<CloudDownloadOutlined />}
          loading={running}
          disabled={!dirSet}
        >
          立即备份
        </Button>
      </Tooltip>
    </Popconfirm>
  );

  return (
    <div style={{ padding: 24, background: '#fff', borderRadius: 8 }}>
      <Card title="备份设置" style={{ marginBottom: 16 }}>
        <Form form={form} layout="vertical" style={{ maxWidth: 640 }}>
          <Form.Item
            name="backup_dir"
            label="备份目录"
            rules={[{ required: true, message: '请输入备份目录' }]}
          >
            <Input
              placeholder="如 /var/backups/gateflow"
              prefix={<DatabaseOutlined />}
            />
          </Form.Item>
          <Form.Item
            name="backup_include_audit_logs"
            valuePropName="checked"
            extra="LLM 调用日志通常很大；建议保持未勾选（仅备份配置/用户/对话等核心数据）"
          >
            <Checkbox>同时备份 LLM 调用日志（可能很大）</Checkbox>
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSave}
              loading={saving}
            >
              保存设置
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="立即备份" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {runButton}
          {running && (
            <Alert
              type="info"
              showIcon
              message="备份进行中，请勿关闭页面..."
            />
          )}
          {error && (
            <Alert
              type="error"
              showIcon
              message={error}
              closable
              onClose={() => setError(null)}
            />
          )}
          {result && (
            <Row gutter={16}>
              <Col span={6}>
                <Statistic title="文件" value={result.filename} />
              </Col>
              <Col span={6}>
                <Statistic title="大小" value={formatBytes(result.size_bytes)} />
              </Col>
              <Col span={6}>
                <Statistic
                  title="耗时"
                  value={formatDuration(result.duration_ms)}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="表数量"
                  value={result.tables_dumped}
                  suffix={
                    result.excluded_audit_logs ? (
                      <span style={{ fontSize: 12, color: '#999' }}>
                        （已排除 audit_logs）
                      </span>
                    ) : null
                  }
                />
              </Col>
            </Row>
          )}
        </Space>
      </Card>

      <Card title="历史备份">
        <Table
          rowKey="filename"
          dataSource={history}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无备份" /> }}
          columns={[
            { title: '文件名', dataIndex: 'filename' },
            {
              title: '大小',
              dataIndex: 'size_bytes',
              width: 140,
              render: (b: number) => formatBytes(b),
            },
            {
              title: '备份时间',
              dataIndex: 'mtime',
              width: 200,
              render: (s: string) => dayjs(s).format('YYYY-MM-DD HH:mm:ss'),
            },
          ]}
        />
      </Card>
    </div>
  );
}
