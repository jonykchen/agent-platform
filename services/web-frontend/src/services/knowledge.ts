import api from './api';
import type { PageResponse } from '@/types/common';
import type {
  KnowledgeDocument,
  DocumentQueryParams,
  DocumentUploadResponse,
  DocumentDetail,
  IndexingStats,
} from '@/types/knowledge';

export const knowledgeService = {
  /** 获取文档列表 */
  async list(params?: DocumentQueryParams): Promise<PageResponse<KnowledgeDocument>> {
    const { data } = await api.get('/knowledge/documents', { params });
    return data;
  },

  /** 获取文档详情 */
  async get(documentId: string): Promise<DocumentDetail> {
    const { data } = await api.get(`/knowledge/documents/${documentId}`);
    return data;
  },

  /** 上传文档 */
  async upload(files: File[]): Promise<DocumentUploadResponse[]> {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    const { data } = await api.post('/knowledge/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  /** 删除文档 */
  async delete(documentId: string): Promise<void> {
    await api.delete(`/knowledge/documents/${documentId}`);
  },

  /** 批量删除文档 */
  async batchDelete(documentIds: string[]): Promise<void> {
    await api.post('/knowledge/documents/batch-delete', { document_ids: documentIds });
  },

  /** 重新索引文档 */
  async reindex(documentId: string): Promise<void> {
    await api.post(`/knowledge/documents/${documentId}/reindex`);
  },

  /** 获取索引统计 */
  async getStats(): Promise<IndexingStats> {
    const { data } = await api.get('/knowledge/stats');
    return data;
  },

  /** 搜索文档内容 */
  async search(query: string, limit?: number): Promise<Array<{ chunk_id: string; document_id: string; document_title: string; content: string; score: number }>> {
    const { data } = await api.get('/knowledge/search', {
      params: { query, limit },
    });
    return data;
  },
};

export default knowledgeService;
