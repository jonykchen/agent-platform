import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useMemo, useCallback } from 'react';
import {
  Card,
  Button,
  Input,
  Select,
  Space,
  Tag,
  Table,
  Modal,
  message,
  Tooltip,
  Badge,
  Typography,
  Progress,
  Statistic,
  Row,
  Col,
  Popconfirm,
  Alert,
} from 'antd';
import {
  Search,
  Plus,
  RefreshCw,
  FileText,
  Trash2,
  Upload,
  Download,
  AlertCircle,
  CheckCircle,
  Clock,
} from 'lucide-react';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import { knowledgeService } from '@/services/knowledge';
import type { KnowledgeDocument, DocumentQueryParams, IndexingStats } from '@/types/knowledge';
import { DocumentUploader } from '@/components/knowledge/DocumentUploader';
import { LoadingState } from '@/components/feedback/LoadingState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageLayout } from '@/components/layout/PageLayout';
import { usePermission, Permissions } from '@/hooks/usePermission';
import { APP_CONFIG } from '@/constants/config';
import { formatDateTime, formatRelativeTime } from '@/utils/date';
import { formatFileSize } from '@/utils/format';

const { Title, Text } = Typography;

export const Route = createFileRoute('/knowledge/')({
  component: KnowledgePage,
});

const statusConfig: Record<string, { color: string; label: string }> = {
  pending: { color: 'default', label: '待处理' },
  indexing: { color: 'processing', label: '索引中' },
  ready: { color: 'success', label: '就绪' },
  failed: { color: 'error', label: '失败' },
};

function KnowledgePage() {
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();
  const canUpload = hasPermission(Permissions.KNOWLEDGE_WRITE);
  const canDelete = hasPermission(Permissions.KNOWLEDGE_WRITE);
  const canReindex = hasPermission(Permissions.KNOWLEDGE_WRITE);

  // 状态
  const [params, setParams] = useState<DocumentQueryParams>({
    pageNumber: 1,
    pageSize: APP_CONFIG.DEFAULT_PAGE_SIZE,
  });
  const [searchText, setSearchText] = useState('');
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  // 查询文档列表
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['knowledge-documents', params],
    queryFn: () => knowledgeService.list(params),
  });

  // 查询索引统计
  const { data: stats } = useQuery({
    queryKey: ['knowledge-stats'],
    queryFn: () => knowledgeService.getStats(),
    staleTime: 30000,
  });

  // 上传文档
  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => knowledgeService.upload(files),
    onSuccess: () => {
      message.success('文档上传成功，正在索引中');
      setUploadModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ['knowledge-documents'] });
      queryClient.invalidateQueries({ queryKey: ['knowledge-stats'] });
    },
    onError: () => {
      message.error('上传失败');
    },
  });

  // 删除文档
  const deleteMutation = useMutation({
    mutationFn: (id: string) => knowledgeService.delete(id),
    onSuccess: () => {
      message.success('文档已删除');
      queryClient.invalidateQueries({ queryKey: ['knowledge-documents'] });
      queryClient.invalidateQueries({ queryKey: ['knowledge-stats'] });
    },
    onError: () => {
      message.error('删除失败');
    },
  });

  // 批量删除
  const batchDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => knowledgeService.batchDelete(ids),
    onSuccess: () => {
      message.success('已批量删除');
      setSelectedRowKeys([]);
      queryClient.invalidateQueries({ queryKey: ['knowledge-documents'] });
      queryClient.invalidateQueries({ queryKey: ['knowledge-stats'] });
    },
  });

  // 重新索引
  const reindexMutation = useMutation({
    mutationFn: (id: string) => knowledgeService.reindex(id),
    onSuccess: () => {
      message.success('已开始重新索引');
      queryClient.invalidateQueries({ queryKey: ['knowledge-documents'] });
    },
    onError: () => {
      message.error('操作失败');
    },
  });

  // 处理搜索
  const handleSearch = useCallback(() => {
    setParams((prev) => ({ ...prev, pageNumber: 1, search: searchText || undefined }));
  }, [searchText]);

  // 处理筛选变化
  const handleFilterChange = useCallback((key: string, value?: string) => {
    setParams((prev) => ({ ...prev, pageNumber: 1, [key]: value }));
  }, []);

  // 处理上传
  const handleUpload = useCallback(async (files: File[]) => {
    await uploadMutation.mutateAsync(files);
  }, [uploadMutation]);

  // 表格列
  const columns: ColumnsType<KnowledgeDocument> = useMemo(() => [
    {
      title: '文档名称',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (title: string) => (
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-gray-400" />
          <Text>{title}</Text>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'content_type',
      key: 'content_type',
      width: 100,
      render: (type: string) => <Tag>{type}</Tag>,
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (size: number) => formatFileSize(size),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config = statusConfig[status];
        return <Tag color={config?.color}>{config?.label || status}</Tag>;
      },
    },
    {
      title: '分块数',
      dataIndex: 'chunk_count',
      key: 'chunk_count',
      width: 80,
      render: (count: number) => count || '-',
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (time: string) => (
        <Tooltip title={formatDateTime(time)}>
          <span className="text-gray-500">{formatRelativeTime(time)}</span>
        </Tooltip>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="重新索引">
            <Button
              type="text"
              size="small"
              icon={<RefreshCw className="w-4 h-4" />}
              disabled={!canReindex || record.status === 'indexing'}
              onClick={() => reindexMutation.mutate(record.id)}
            />
          </Tooltip>
          <Popconfirm
            title="确认删除此文档？"
            onConfirm={() => deleteMutation.mutate(record.id)}
            disabled={!canDelete}
          >
            <Tooltip title="删除">
              <Button
                type="text"
                size="small"
                danger
                icon={<Trash2 className="w-4 h-4" />}
                disabled={!canDelete}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ], [canReindex, canDelete, reindexMutation, deleteMutation]);

  // 分页变化
  const handleTableChange = useCallback((pagination: TablePaginationConfig) => {
    setParams((prev) => ({
      ...prev,
      pageNumber: pagination.current || 1,
      pageSize: pagination.pageSize || APP_CONFIG.DEFAULT_PAGE_SIZE,
    }));
  }, []);

  return (
    <PageLayout>
    <div className="space-y-4">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Title level={4} className="!mb-2">
            知识库管理
          </Title>
          <Text type="secondary">
            上传和管理知识文档，支持 Agent RAG 检索增强
          </Text>
        </div>
        <Button
          type="primary"
          icon={<Upload className="w-4 h-4" />}
          onClick={() => setUploadModalOpen(true)}
          disabled={!canUpload}
        >
          上传文档
        </Button>
      </div>

      {/* 统计卡片 */}
      {stats && (
        <Card className="mb-4">
          <Row gutter={16}>
            <Col span={4}>
              <Statistic
                title="总文档"
                value={stats.total_documents}
                prefix={<FileText className="w-5 h-5 text-blue-500" />}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="就绪"
                value={stats.ready}
                prefix={<CheckCircle className="w-5 h-5 text-green-500" />}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="索引中"
                value={stats.indexing}
                prefix={<Clock className="w-5 h-5 text-blue-500" />}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="待处理"
                value={stats.pending}
                prefix={<Clock className="w-5 h-5 text-gray-400" />}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="失败"
                value={stats.failed}
                prefix={<AlertCircle className="w-5 h-5 text-red-500" />}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="总大小"
                value={stats.total_size_bytes}
                formatter={(v) => formatFileSize(Number(v))}
              />
            </Col>
          </Row>
        </Card>
      )}

      {/* 筛选栏 */}
      <Card className="mb-4">
        <Space wrap size="middle">
          <Input.Search
            placeholder="搜索文档名称"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onSearch={handleSearch}
            style={{ width: 250 }}
            prefix={<Search className="w-4 h-4 text-gray-400" />}
            allowClear
          />
          <Select
            placeholder="状态筛选"
            value={params.status}
            onChange={(value) => handleFilterChange('status', value)}
            style={{ width: 120 }}
            allowClear
            options={[
              { value: 'pending', label: '待处理' },
              { value: 'indexing', label: '索引中' },
              { value: 'ready', label: '就绪' },
              { value: 'failed', label: '失败' },
            ]}
          />
          <Select
            placeholder="文件类型"
            value={params.content_type}
            onChange={(value) => handleFilterChange('content_type', value)}
            style={{ width: 120 }}
            allowClear
            options={[
              { value: 'pdf', label: 'PDF' },
              { value: 'doc', label: 'Word' },
              { value: 'txt', label: '文本' },
              { value: 'md', label: 'Markdown' },
            ]}
          />
          <Button
            icon={<RefreshCw className="w-4 h-4" />}
            onClick={() => refetch()}
            loading={isFetching}
          >
            刷新
          </Button>
          {selectedRowKeys.length > 0 && canDelete && (
            <Popconfirm
              title={`确认删除选中的 ${selectedRowKeys.length} 个文档？`}
              onConfirm={() => batchDeleteMutation.mutate(selectedRowKeys as string[])}
            >
              <Button danger icon={<Trash2 className="w-4 h-4" />}>
                批量删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      </Card>

      {/* 文档列表 */}
      <Card>
        <Table
          columns={columns}
          dataSource={data?.items || []}
          rowKey="id"
          loading={isLoading}
          pagination={{
            current: params.pageNumber,
            pageSize: params.pageSize,
            total: data?.total_count || 0,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 个文档`,
          }}
          onChange={handleTableChange}
          rowSelection={
            canDelete
              ? {
                  selectedRowKeys,
                  onChange: setSelectedRowKeys,
                }
              : undefined
          }
          locale={{
            emptyText: (
              <EmptyState
                description="暂无知识文档"
                action={
                  canUpload
                    ? {
                        label: '上传文档',
                        onClick: () => setUploadModalOpen(true),
                      }
                    : undefined
                }
              />
            ),
          }}
        />
      </Card>

      {/* 上传弹窗 */}
      <Modal
        title="上传文档"
        open={uploadModalOpen}
        onCancel={() => setUploadModalOpen(false)}
        footer={null}
        width={600}
      >
        <DocumentUploader onUpload={handleUpload} />
      </Modal>
    </div>
    </PageLayout>
  );
}

export default Route;