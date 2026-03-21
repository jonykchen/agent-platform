import { useCallback, useState } from 'react';
import { Upload, Button, Progress, message, Typography } from 'antd';
import { Upload as UploadIcon, X, FileIcon, CheckCircle } from 'lucide-react';
import type { UploadFile, UploadProps } from 'antd/es/upload/interface';
import clsx from 'clsx';
import { APP_CONFIG } from '@/constants/config';

const { Text } = Typography;

export interface FileUploadProps {
  accept?: string;
  multiple?: boolean;
  maxCount?: number;
  maxSizeMB?: number;
  onUpload: (files: File[]) => Promise<void>;
  uploading?: boolean;
  className?: string;
  hint?: string;
}

export function FileUpload({
  accept,
  multiple = true,
  maxCount = APP_CONFIG.MAX_FILES_PER_UPLOAD,
  maxSizeMB = APP_CONFIG.MAX_FILE_SIZE_MB,
  onUpload,
  uploading = false,
  className,
  hint,
}: FileUploadProps) {
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);

  const handleBeforeUpload = useCallback(
    (file: File) => {
      // 检查文件大小
      const isLtMaxSize = file.size / 1024 / 1024 < maxSizeMB;
      if (!isLtMaxSize) {
        message.error(`文件 ${file.name} 超过 ${maxSizeMB}MB 限制`);
        return Upload.LIST_IGNORE;
      }

      // 检查文件数量
      if (fileList.length >= maxCount) {
        message.error(`最多上传 ${maxCount} 个文件`);
        return Upload.LIST_IGNORE;
      }

      return false; // 阻止自动上传
    },
    [fileList.length, maxCount, maxSizeMB]
  );

  const handleRemove = useCallback(
    (file: UploadFile) => {
      const index = fileList.indexOf(file);
      const newFileList = fileList.slice();
      newFileList.splice(index, 1);
      setFileList(newFileList);
    },
    [fileList]
  );

  const handleUpload = useCallback(async () => {
    if (fileList.length === 0) {
      message.warning('请先选择文件');
      return;
    }

    const files = fileList.map((f) => f.originFileObj as File).filter(Boolean);

    try {
      setUploadProgress(0);
      // 模拟进度
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => Math.min(prev + 10, 90));
      }, 100);

      await onUpload(files);

      clearInterval(progressInterval);
      setUploadProgress(100);

      message.success('上传成功');
      setFileList([]);
    } catch (error) {
      message.error('上传失败');
    } finally {
      setTimeout(() => setUploadProgress(0), 500);
    }
  }, [fileList, onUpload]);

  const uploadProps: UploadProps = {
    accept,
    multiple,
    fileList,
    beforeUpload: handleBeforeUpload,
    onRemove: handleRemove,
    onChange: ({ fileList: newFileList }) => setFileList(newFileList),
    showUploadList: {
      showDownloadIcon: false,
      showRemoveIcon: true,
      removeIcon: <X className="w-4 h-4" />,
    },
  };

  return (
    <div className={clsx('space-y-4', className)}>
      <Upload.Dragger {...uploadProps} className="!border-dashed !border-gray-300 hover:!border-blue-400">
        <div className="p-6">
          <UploadIcon className="w-10 h-10 mx-auto text-gray-400 mb-3" />
          <Text strong className="block mb-1">
            点击或拖拽文件到此区域上传
          </Text>
          <Text type="secondary" className="text-sm">
            {hint || `支持单个文件最大 ${maxSizeMB}MB，最多 ${maxCount} 个文件`}
          </Text>
        </div>
      </Upload.Dragger>

      {fileList.length > 0 && (
        <div className="flex items-center justify-between">
          <Text type="secondary">
            已选择 {fileList.length} 个文件
          </Text>
          <Button
            type="primary"
            onClick={handleUpload}
            loading={uploading}
            disabled={uploadProgress > 0 && uploadProgress < 100}
          >
            开始上传
          </Button>
        </div>
      )}

      {uploadProgress > 0 && uploadProgress < 100 && (
        <Progress percent={uploadProgress} status="active" />
      )}
    </div>
  );
}

export interface UploadProgressProps {
  file: string;
  progress: number;
  status: 'uploading' | 'success' | 'error';
  onRemove?: () => void;
}

export function UploadProgress({ file, progress, status, onRemove }: UploadProgressProps) {
  return (
    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
      <FileIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <Text ellipsis className="block text-sm">
          {file}
        </Text>
        {status === 'uploading' && (
          <Progress percent={progress} size="small" showInfo={false} />
        )}
      </div>
      {status === 'success' && <CheckCircle className="w-5 h-5 text-green-500" />}
      {status === 'error' && <X className="w-5 h-5 text-red-500" />}
      {onRemove && (
        <Button type="text" size="small" icon={<X className="w-4 h-4" />} onClick={onRemove} />
      )}
    </div>
  );
}

export default FileUpload;
