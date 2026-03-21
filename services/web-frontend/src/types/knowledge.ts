/** 知识库文档 */
export interface KnowledgeDocument {
  id: string;
  tenant_id: string;
  title: string;
  content_type: string;
  file_size: number;
  status: 'pending' | 'indexing' | 'ready' | 'failed';
  chunk_count: number;
  indexed_at?: string;
  created_at: string;
  updated_at?: string;
  error_message?: string;
  metadata?: Record<string, unknown>;
}

/** 文档查询参数 */
export interface DocumentQueryParams {
  status?: 'pending' | 'indexing' | 'ready' | 'failed';
  content_type?: string;
  search?: string;
  page_number?: number;
  page_size?: number;
}

/** 文档上传响应 */
export interface DocumentUploadResponse {
  id: string;
  title: string;
  status: 'pending';
  message: string;
}

/** 文档详情 */
export interface DocumentDetail extends KnowledgeDocument {
  chunks: DocumentChunk[];
  indexing_progress?: number;
}

/** 文档分块 */
export interface DocumentChunk {
  id: string;
  document_id: string;
  content: string;
  chunk_index: number;
  token_count: number;
  embedding_status: 'pending' | 'completed' | 'failed';
  created_at: string;
}

/** 索引状态统计 */
export interface IndexingStats {
  total_documents: number;
  pending: number;
  indexing: number;
  ready: number;
  failed: number;
  total_chunks: number;
  total_size_bytes: number;
}
