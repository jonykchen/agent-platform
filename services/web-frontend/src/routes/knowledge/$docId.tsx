import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Descriptions,
  Button,
  Space,
  Typography,
  Tag,
  Progress,
  List,
  Tooltip,
  message,
  Alert,
  Spin,
  Modal,
} from 'antd';
import {
  ArrowLeft,
  RefreshCw,
  Trash2,
  FileText,
  CheckCircle,
  AlertCircle,
  Clock,
  Download,
} from 'lucide-react';
import { knowledgeService } from '@/services/knowledge';
import type { DocumentDetail, DocumentChunk } from '@/types/knowledge';
import { LoadingState } from '@/components/feedback/LoadingState';
import { PageLayout } from '@/components/layout/PageLayout';
import { usePermission, Permissions } from '@/hooks/usePermission';
import { formatDateTime, formatRelativeTime } from '@/utils/date';
import { formatFileSize } from '@/utils/format';

const { Title, Text } = Typography;

export const Route = createFileRoute('/knowledge/$docId')({
  component: DocumentDetailPage,
});

const statusConfig: Record<string, { color: string; label: string }> = {
  pending: { color: 'default', label: '待处理' },
  indexing: { color: 'processing', label: '索引中' },
  ready: { color: 'success', label: '就绪' },
  failed: { color: 'error', label: '失败' },
};

const embeddingStatusConfig: Record<string, { color: string; icon: React.ReactNode }> = {
  pending: { color: 'default', icon: <Clock className="w-4 h-4" /> },
  completed: { color: 'success', icon: <CheckCircle className="w-4 h-4" /> },
  failed: { color: 'error', icon: <AlertCircle className="w-4 h-4" /> },
};

function DocumentDetailPage() {
  const { docId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();
  const canDelete = hasPermission(Permissions.KNOWLEDGE_WRITE);
  const canReindex = hasPermission(Permissions.KNOWLEDGE_WRITE);

  // 查询文档详情
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['knowledge-document', docId],
    queryFn: () => knowledgeService.get(docId),
    staleTime: 30000,
  });

  // 删除
  const deleteMutation = useMutation({
    mutationFn: () => knowledgeService.delete(docId),
    onSuccess: () => {
      message.success('文档已删除');
      navigate({ to: '/knowledge' });
      queryClient.invalidateQueries({ queryKey: ['knowledge-documents'] });
    },
  });

  // 重新索引
  const reindexMutation = useMutation({
    mutationFn: () => knowledgeService.reindex(docId),
    onSuccess: () => {
      message.success('已开始重新索引');
      queryClient.invalidateQueries({ queryKey: ['knowledge-document', docId] });
    },
  });

  const handleDelete = useCallback(() => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后将无法恢复，确定要删除此文档吗？',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => deleteMutation.mutate(),
    });
  }, [deleteMutation]);

  const handleBack = useCallback(() => {
    navigate({ to: '/knowledge' });
  }, [navigate]);

  if (isLoading) {
    return <PageLayout><LoadingState /></PageLayout>;
  }

  if (!data) {
    return (
      <PageLayout>
      <div className="space-y-4">
        <Alert type="error" message="文档不存在或已被删除" showIcon />
        <Button type="link" onClick={handleBack} className="mt-4">
          返回知识库列表
        </Button>
      </div>
      </PageLayout>
    );
  }

  const status = statusConfig[data.status] || statusConfig.pending;

  return (
    <PageLayout>
    <div className="space-y-4">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button type="text" icon={<ArrowLeft className="w-5 h-5" />} onClick={handleBack} />
          <div>
            <Title level={4} className="!mb-2">
              {data.title}
            </Title>
            <Space>
              <Tag color={status.color}>{status.label}</Tag>
              <Text type="secondary">{data.content_type}</Text>
              <Text type="secondary">{formatFileSize(data.file_size)}</Text>
            </Space>
          </div>
        </div>
        <Space>
          <Button
            icon={<RefreshCw className="w-4 h-4" />}
            onClick={() => reindexMutation.mutate()}
            disabled={!canReindex || data.status === 'indexing'}
            loading={reindexMutation.isPending}
          >
            重新索引
          </Button>
          <Button
            danger
            icon={<Trash2 className="w-4 h-4" />}
            onClick={handleDelete}
            disabled={!canDelete}
          >
            删除
          </Button>
        </Space>
      </div>

      {/* 基本信息 */}
      <Card className="mb-4">
        <Descriptions column={3} bordered size="small">
          <Descriptions.Item label="文档ID">
            <Text copyable className="text-xs">
              {data.id}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="租户ID">{data.tenant_id}</Descriptions.Item>
          <Descriptions.Item label="文件类型">{data.content_type}</Descriptions.Item>
          <Descriptions.Item label="文件大小">{formatFileSize(data.file_size)}</Descriptions.Item>
          <Descriptions.Item label="分块数量">{data.chunk_count}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={status.color}>{status.label}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="上传时间">{formatDateTime(data.created_at)}</Descriptions.Item>
          <Descriptions.Item label="索引时间">
            {data.indexed_at ? formatDateTime(data.indexed_at) : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {data.updated_at ? formatDateTime(data.updated_at) : '-'}
          </Descriptions.Item>
          {data.error_message && (
            <Descriptions.Item label="错误信息" span={3}>
              <Text type="danger">{data.error_message}</Text>
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      {/* 索引进度 */}
      {data.status === 'indexing' && (
        <Card className="mb-4">
          <div className="flex items-center gap-4">
            <Clock className="w-5 h-5 text-blue-500 animate-spin" />
            <div className="flex-1">
              <Text>正在索引文档...</Text>
              {data.indexing_progress && (
                <Progress percent={data.indexing_progress} status="active" className="mt-2" />
              )}
            </div>
          </div>
        </Card>
      )}

      {/* 分块列表 */}
      <Card title={`文档分块 (${data.chunks?.length || 0})`}>
        {data.chunks && data.chunks.length > 0 ? (
          <List
            dataSource={data.chunks}
            renderItem={(chunk: DocumentChunk) => {
              const embeddingStatus = embeddingStatusConfig[chunk.embedding_status] || embeddingStatusConfig.pending;
              return (
                <List.Item>
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-gray-100 rounded flex items-center justify-center">
                      <Text className="text-xs text-gray-500">{chunk.chunk_index + 1}</Text>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Text type="secondary" className="text-xs">
                          Token: {chunk.token_count}
                        </Text>
                        <Tag color={embeddingStatus.color} icon={embeddingStatus.icon}>
                          {chunk.embedding_status}
                        </Tag>
                      </div>
                      <Text
                        ellipsis={{ rows: 3 }}
                        className="text-sm text-gray-600 bg-gray-50 p-2 rounded"
                      >
                        {chunk.content.slice(0, 500)}...
                      </Text>
                    </div>
                  </div>
                </List.Item>
              );
            }}
            pagination={
              data.chunks.length > 20
                ? {
                    pageSize: 20,
                    showSizeChanger: true,
                  }
                : false
            }
          />
        ) : (
          <EmptyState description="暂无分块数据" />
        )}
      </Card>
    </div>
    </PageLayout>
  );
}

export default Route;