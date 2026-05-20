import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, useCallback, useMemo, useEffect } from 'react';
import {
  Card,
  Row,
  Col,
  Statistic,
  Select,
  Button,
  Space,
  Alert,
  List,
  Tag,
  Badge,
  message,
  Switch,
} from 'antd';
import {
  RefreshCw,
  MessageSquare,
  Play,
  Coins,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Users,
  Clock,
  Bell,
} from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import { PageLayout } from '@/components/layout/PageLayout';
import {
  getDashboardStats,
  getDailyRunStats,
  getDailyCostStats,
  getTokenDistribution,
  getActiveAlerts,
} from '@/services/dashboard';
import type { TimeRange, DashboardStats, DailyRunStats, DailyCostStats, TokenDistribution } from '@/services/dashboard';
import { useWebSocket } from '@/hooks/useWebSocket';
import { formatNumber, formatCurrency, formatPercent } from '@/utils/format';
import { formatDateTime } from '@/utils/date';

export const Route = createFileRoute('/dashboard/')({
  component: DashboardPage,
});

// 刷新间隔选项
const REFRESH_INTERVALS = [
  { value: 10000, label: '10秒' },
  { value: 30000, label: '30秒' },
  { value: 60000, label: '1分钟' },
  { value: 300000, label: '5分钟' },
  { value: 0, label: '关闭' },
];

// 时间范围选项
const TIME_RANGES: { value: TimeRange; label: string }[] = [
  { value: '24h', label: '最近24小时' },
  { value: '7d', label: '最近7天' },
  { value: '30d', label: '最近30天' },
  { value: '90d', label: '最近90天' },
];

interface RealTimeAlert {
  id: string;
  type: 'error' | 'warning' | 'info';
  message: string;
  source: string;
  created_at: string;
}

function DashboardPage() {
  const queryClient = useQueryClient();
  const [timeRange, setTimeRange] = useState<TimeRange>('7d');
  const [refreshInterval, setRefreshInterval] = useState<number>(30000);
  const [realTimeAlerts, setRealTimeAlerts] = useState<RealTimeAlert[]>([]);

  // 计算日期范围
  const dateRange = useMemo(() => {
    const end = new Date();
    const start = new Date();
    const days = timeRange === '24h' ? 1 : parseInt(timeRange.replace('d', ''));
    start.setDate(start.getDate() - days);
    return {
      startDate: start.toISOString().split('T')[0],
      endDate: end.toISOString().split('T')[0],
    };
  }, [timeRange]);

  // 查询统计数据
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats', timeRange],
    queryFn: () => getDashboardStats(timeRange),
  });

  // 查询每日运行趋势
  const { data: dailyRuns } = useQuery({
    queryKey: ['daily-runs', dateRange],
    queryFn: () => getDailyRunStats(dateRange),
  });

  // 查询每日成本趋势
  const { data: dailyCosts } = useQuery({
    queryKey: ['daily-costs', dateRange],
    queryFn: () => getDailyCostStats(dateRange),
  });

  // 查询 Token 分布
  const { data: tokenDistribution } = useQuery({
    queryKey: ['token-distribution', dateRange],
    queryFn: () => getTokenDistribution(dateRange),
  });

  // 查询活跃告警
  const { data: activeAlerts } = useQuery({
    queryKey: ['active-alerts'],
    queryFn: getActiveAlerts,
    refetchInterval: 10000,
  });

  // WebSocket 实时告警
  const wsUrl = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws'}/dashboard`;
  useWebSocket({
    url: wsUrl,
    onMessage: (data: { type: string; alert?: RealTimeAlert }) => {
      if (data.type === 'alert' && data.alert) {
        setRealTimeAlerts((prev) => [data.alert!, ...prev].slice(0, 10));
        message.warning(data.alert.message);
      }
    },
  });

  // 自动刷新
  useEffect(() => {
    if (refreshInterval <= 0) return;

    const timer = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['daily-runs'] });
      queryClient.invalidateQueries({ queryKey: ['daily-costs'] });
      queryClient.invalidateQueries({ queryKey: ['token-distribution'] });
    }, refreshInterval);

    return () => clearInterval(timer);
  }, [refreshInterval, queryClient]);

  // 手动刷新
  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  }, [queryClient]);

  // 运行趋势图配置
  const runTrendOption = useMemo(() => ({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: ['总运行', '成功', '失败'],
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dailyRuns?.map((d) => d.date) || [],
    },
    yAxis: {
      type: 'value',
    },
    series: [
      {
        name: '总运行',
        type: 'line',
        data: dailyRuns?.map((d) => d.runs) || [],
        smooth: true,
        itemStyle: { color: '#1890ff' },
        areaStyle: { color: 'rgba(24, 144, 255, 0.1)' },
      },
      {
        name: '成功',
        type: 'line',
        data: dailyRuns?.map((d) => d.successful) || [],
        smooth: true,
        itemStyle: { color: '#52c41a' },
      },
      {
        name: '失败',
        type: 'line',
        data: dailyRuns?.map((d) => d.failed) || [],
        smooth: true,
        itemStyle: { color: '#ff4d4f' },
      },
    ],
  }), [dailyRuns]);

  // 成本趋势图配置
  const costTrendOption = useMemo(() => ({
    tooltip: {
      trigger: 'axis',
      formatter: (params: Array<{ name: string; value: number; seriesName: string }>) => {
        const date = params[0].name;
        const cost = params.find((p) => p.seriesName === '成本');
        const tokens = params.find((p) => p.seriesName === 'Token数');
        return `
          <div>
            <div style="font-weight: bold">${date}</div>
            <div>成本: ${formatCurrency(cost?.value || 0)}</div>
            <div>Token: ${formatNumber(tokens?.value || 0)}</div>
          </div>
        `;
      },
    },
    legend: {
      data: ['成本', 'Token数'],
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dailyCosts?.map((d) => d.date) || [],
    },
    yAxis: [
      {
        type: 'value',
        name: '成本 (USD)',
        axisLabel: {
          formatter: (value: number) => `$${value}`,
        },
      },
      {
        type: 'value',
        name: 'Token',
        axisLabel: {
          formatter: (value: number) => formatNumber(value),
        },
      },
    ],
    series: [
      {
        name: '成本',
        type: 'bar',
        data: dailyCosts?.map((d) => d.cost_usd) || [],
        itemStyle: { color: '#722ed1' },
      },
      {
        name: 'Token数',
        type: 'line',
        yAxisIndex: 1,
        data: dailyCosts?.map((d) => d.tokens) || [],
        itemStyle: { color: '#13c2c2' },
      },
    ],
  }), [dailyCosts]);

  // Token 分布饼图配置
  const tokenPieOption = useMemo(() => ({
    tooltip: {
      trigger: 'item',
      formatter: (params: { name: string; value: number; percent: number; data: { cost_usd: number } }) => {
        return `
          <div>
            <div style="font-weight: bold">${params.name}</div>
            <div>Token: ${formatNumber(params.value)}</div>
            <div>占比: ${params.percent.toFixed(1)}%</div>
            <div>成本: ${formatCurrency(params.data.cost_usd)}</div>
          </div>
        `;
      },
    },
    legend: {
      orient: 'vertical',
      left: 'left',
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          show: true,
          formatter: '{b}: {d}%',
        },
        data: tokenDistribution?.map((d) => ({
          name: d.model,
          value: d.tokens,
          cost_usd: d.cost_usd,
        })) || [],
      },
    ],
  }), [tokenDistribution]);

  return (
    <PageLayout>
      <div className="space-y-4">
        {/* 工具栏 */}
        <div className="flex justify-between items-center">
          <Space>
            <Select
              value={timeRange}
              onChange={setTimeRange}
              options={TIME_RANGES}
              style={{ width: 150 }}
            />
            <span className="text-gray-500 text-sm">刷新间隔:</span>
            <Select
              value={refreshInterval}
              onChange={setRefreshInterval}
              options={REFRESH_INTERVALS}
              style={{ width: 100 }}
            />
          </Space>
          <Button icon={<RefreshCw className="w-4 h-4" />} onClick={handleRefresh}>
            刷新
          </Button>
        </div>

        {/* 统计卡片 */}
        <Row gutter={16}>
          <Col span={6}>
            <Card>
              <Statistic
                title="总会话数"
                value={stats?.total_sessions || 0}
                prefix={<MessageSquare className="w-5 h-5 text-blue-500" />}
                loading={statsLoading}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="总运行次数"
                value={stats?.total_runs || 0}
                prefix={<Play className="w-5 h-5 text-green-500" />}
                loading={statsLoading}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="Token 消耗"
                value={stats?.total_tokens || 0}
                prefix={<Coins className="w-5 h-5 text-purple-500" />}
                formatter={(value) => formatNumber(Number(value))}
                loading={statsLoading}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="总成本"
                value={stats?.total_cost_usd || 0}
                precision={2}
                prefix={<DollarSign className="w-5 h-5 text-orange-500" />}
                formatter={(value) => `$${formatNumber(Number(value))}`}
                loading={statsLoading}
              />
            </Card>
          </Col>
        </Row>

        {/* 次要统计卡片 */}
        <Row gutter={16}>
          <Col span={6}>
            <Card>
              <Statistic
                title="成功率"
                value={stats?.success_rate || 0}
                suffix="%"
                prefix={
                  (stats?.success_rate || 0) >= 95 ? (
                    <TrendingUp className="w-5 h-5 text-green-500" />
                  ) : (
                    <TrendingDown className="w-5 h-5 text-red-500" />
                  )
                }
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="平均响应时间"
                value={stats?.avg_response_time_ms || 0}
                suffix="ms"
                prefix={<Clock className="w-5 h-5 text-blue-500" />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="活跃用户"
                value={stats?.active_users || 0}
                prefix={<Users className="w-5 h-5 text-purple-500" />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="待审批"
                value={stats?.pending_approvals || 0}
                prefix={<Bell className="w-5 h-5 text-orange-500" />}
                valueStyle={{ color: (stats?.pending_approvals || 0) > 10 ? '#ff4d4f' : undefined }}
              />
            </Card>
          </Col>
        </Row>

        {/* 图表区域 */}
        <Row gutter={16}>
          <Col span={16}>
            <Card title="运行趋势">
              <ReactECharts option={runTrendOption} style={{ height: 300 }} />
            </Card>
          </Col>
          <Col span={8}>
            <Card title="Token 按模型分布">
              <ReactECharts option={tokenPieOption} style={{ height: 300 }} />
            </Card>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={24}>
            <Card title="成本趋势">
              <ReactECharts option={costTrendOption} style={{ height: 300 }} />
            </Card>
          </Col>
        </Row>

        {/* 实时告警 */}
        <Row gutter={16}>
          <Col span={12}>
            <Card
              title={
                <span>
                  <Bell className="w-4 h-4 inline mr-2" />
                  实时告警
                  {realTimeAlerts.length > 0 && (
                    <Badge count={realTimeAlerts.length} className="ml-2" />
                  )}
                </span>
              }
            >
              <List
                dataSource={realTimeAlerts}
                renderItem={(alert) => (
                  <List.Item>
                    <Alert
                      message={alert.message}
                      description={`${alert.source} - ${formatDateTime(alert.created_at)}`}
                      type={alert.type === 'error' ? 'error' : alert.type === 'warning' ? 'warning' : 'info'}
                      showIcon
                    />
                  </List.Item>
                )}
                locale={{ emptyText: '暂无告警' }}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card title="系统告警">
              <List
                dataSource={activeAlerts || []}
                renderItem={(alert) => (
                  <List.Item>
                    <List.Item.Meta
                      avatar={
                        <Tag
                          color={
                            alert.type === 'error'
                              ? 'error'
                              : alert.type === 'warning'
                              ? 'warning'
                              : 'default'
                          }
                        >
                          {alert.type}
                        </Tag>
                      }
                      title={alert.message}
                      description={`${alert.source} - ${formatDateTime(alert.created_at)}`}
                    />
                  </List.Item>
                )}
                locale={{ emptyText: '暂无告警' }}
              />
            </Card>
          </Col>
        </Row>
      </div>
    </PageLayout>
  );
}

export default Route;
