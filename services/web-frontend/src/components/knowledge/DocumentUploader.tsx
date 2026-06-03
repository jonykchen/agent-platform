import { useCallback, useState } from 'react';
import { Upload, Button, message, Typography, Space, Alert, Tooltip } from 'antd';
import { Upload as UploadIcon, FileIcon, X, CheckCircle, AlertCircle } from 'lucide-react';
import type { UploadFile } from 'antd/es/upload/interface';
import clsx from 'clsx';
import { APP_CONFIG } from '@/constants/config';

const { Text, Title } = Typography;

export interface DocumentUploaderProps {
  onUpload: (files: File[]) => Promise<void>;
  accept?: string;
  maxSizeMB?: number;
  maxCount?: number;
  className?: string;
}

interface UploadItem {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  progress?: number;
  error?: string;
}

export function DocumentUploader({
  onUpload,
  accept = '.pdf,.doc,.docx,.txt,.md,.json,.csv',
  maxSizeMB = APP_CONFIG.MAX_FILE_SIZE_MB,
  maxCount = APP_CONFIG.MAX_FILES_PER_UPLOAD,
  className,
}: DocumentUploaderProps) {
  const [uploadItems, setUploadItems] = useState<UploadItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const handleBeforeUpload = useCallback(
    (file: File) => {
      const isLtMaxSize = file.size / 1024 / 1024 < maxSizeMB;
      if (!isLtMaxSize) {
        message.error(`文件 ${file.name} 超过 ${maxSizeMB}MB 限制`);
        return Upload.LIST_IGNORE;
      }

      if (uploadItems.length >= maxCount) {
        message.error(`最多上传 ${maxCount} 个文件`);
        return Upload.LIST_IGNORE;
      }

      setUploadItems((prev) => [
        ...prev,
        { file, status: 'pending' },
      ]);

      return false;
    },
    [uploadItems.length, maxCount, maxSizeMB]
  );

  const handleRemove = useCallback((index: number) => {
    setUploadItems((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleUpload = useCallback(async () => {
    if (uploadItems.length === 0) {
      message.warning('请先选择文件');
      return;
    }

    const files = uploadItems.map((item) => item.file);

    setIsUploading(true);
    setUploadItems((prev) => prev.map((item) => ({ ...item, status: 'uploading' as const })));

    try {
      await onUpload(files);
      setUploadItems((prev) => prev.map((item) => ({ ...item, status: 'success' as const })));
      message.success('文档上传成功');
      setTimeout(() => setUploadItems([]), 2000);
    } catch (error) {
      setUploadItems((prev) =>
        prev.map((item) => ({
          ...item,
          status: 'error' as const,
          error: error instanceof Error ? error.message : '上传失败',
        }))
      );
      message.error('上传失败');
    } finally {
      setIsUploading(false);
    }
  }, [uploadItems, onUpload]);

  const handleClear = useCallback(() => {
    setUploadItems([]);
  }, []);

  const hasFiles = uploadItems.length > 0;

  return (
    <div className={clsx('space-y-4', className)}>
      <Title level={5} className="!mb-2">
        上传文档
      </Title>

      <Upload.Dragger
        accept={accept}
        beforeUpload={handleBeforeUpload}
        showUploadList={false}
        multiple
        className="!border-dashed"
      >
        <div className="p-4">
          <UploadIcon className="w-8 h-8 mx-auto text-gray-400 mb-2" />
          <Text className="block">点击或拖拽文件到此区域上传</Text>
          <Text type="secondary" className="text-xs">
            支持 PDF、Word、TXT、Markdown 等格式，单个文件最大 {maxSizeMB}MB
          </Text>
        </div>
      </Upload.Dragger>

      {hasFiles && (
        <>
          <Alert
            type="info"
            message={
              <span>
                已选择 <strong>{uploadItems.length}</strong> 个文件
              </span>
            }
            className="!py-2"
          />

          <div className="space-y-2 max-h-60 overflow-auto">
            {uploadItems.map((item, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
              >
                <FileIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <Text ellipsis className="block text-sm">
                    {item.file.name}
                  </Text>
                  <Text type="secondary" className="text-xs">
                    {(item.file.size / 1024).toFixed(1)} KB
                  </Text>
                </div>
                {item.status === 'success' && (
                  <CheckCircle className="w-5 h-5 text-green-500" />
                )}
                {item.status === 'error' && (
                  <Tooltip title={item.error}>
                    <AlertCircle className="w-5 h-5 text-red-500" />
                  </Tooltip>
                )}
                {!isUploading && item.status === 'pending' && (
                  <Button
                    type="text"
                    size="small"
                    icon={<X className="w-4 h-4" />}
                    onClick={() => handleRemove(index)}
                  />
                )}
              </div>
            ))}
          </div>

          <Space>
            <Button type="primary" onClick={handleUpload} loading={isUploading}>
              开始上传
            </Button>
            <Button onClick={handleClear} disabled={isUploading}>
              清空
            </Button>
          </Space>
        </>
      )}
    </div>
  );
}

export default DocumentUploader;
