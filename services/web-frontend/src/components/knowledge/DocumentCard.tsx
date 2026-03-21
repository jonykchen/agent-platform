import { Card, Tag, Progress, Tooltip, Typography } from 'antd';
import { FileText, RefreshCw, Trash2, Eye, AlertCircle } from 'lucide-react';
import { formatDateTime } from '@/utils/date';
import { formatFileSize } from '@/utils/format';
import type { KnowledgeDocument } from '@/types/knowledge';

const { Text } = Typography;

export interface DocumentCardProps {
  document: KnowledgeDocument;
  onReindex?: (id: string) => void;
  onDelete?: (id: string) => void;
  onView?: (id: string) => void;
}

const statusConfig: Record<string, { color: string; label: string }> = {
  pending: { color: 'default', label: '待处理' },
  indexing: { color: 'processing', label: '索引中' },
  ready: { color: 'success', label: '就绪' },
  failed: { color: 'error', label: '失败' },
};

export function DocumentCard({ document, onReindex, onDelete, onView }: DocumentCardProps) {
  const status = statusConfig[document.status] || statusConfig.pending;

  return (
    <Card
      className="hover:shadow-md transition-shadow"
      actions={[
        <Tooltip key="view" title="查看详情">
          <Eye
            className="w-4 h-4 cursor-pointer text-gray-500 hover:text-blue-500"
            onClick={() => onView?.(document.id)}
          />
        </Tooltip>,
        <Tooltip key="reindex" title="重新索引">
          <RefreshCw
            className={`w-4 h-4 cursor-pointer ${
              document.status === 'indexing'
                ? 'text-gray-300 cursor-not-allowed'
                : 'text-gray-500 hover:text-blue-500'
            }`}
            onClick={() => document.status !== 'indexing' && onReindex?.(document.id)}
          />
        </Tooltip>,
        <Tooltip key="delete" title="删除">
          <Trash2
            className="w-4 h-4 cursor-pointer text-gray-500 hover:text-red-500"
            onClick={() => onDelete?.(document.id)}
          />
        </Tooltip>,
      ]}
    >
      <div className="flex items-start gap-3">
        {/* 文件图标 */}
        <div className="p-2 bg-blue-50 rounded-lg">
          <FileText className="w-6 h-6 text-blue-500" />
        </div>

        {/* 文件信息 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Text strong ellipsis className="flex-1">
              {document.title}
            </Text>
            <Tag color={status.color}>{status.label}</Tag>
          </div>

          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span>{formatFileSize(document.file_size)}</span>
            <span>{document.content_type}</span>
            {document.chunk_count > 0 && <span>{document.chunk_count} 分块</span>}
          </div>

          {document.status === 'indexing' && (
            <Progress
              percent={50}
              size="small"
              status="active"
              className="mt-2"
            />
          )}

          {document.status === 'failed' && document.error_message && (
            <div className="flex items-center gap-1 mt-2 text-red-500 text-xs">
              <AlertCircle className="w-3 h-3" />
              <Text type="danger" ellipsis>
                {document.error_message}
              </Text>
            </div>
          )}

          <div className="mt-2 text-xs text-gray-400">
            <Tooltip title={`创建: ${formatDateTime(document.created_at)}`}>
              <span>上传于 {formatDateTime(document.created_at)}</span>
            </Tooltip>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default DocumentCard;
