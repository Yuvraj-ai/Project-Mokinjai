import apiClient from './client'

export interface KnowledgeBase {
  id: string
  workspace_id: string
  name: string
  description: string | null
  type: string
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface DocumentMetadata {
  original_filename?: string
  uploaded_by?: string
  declared_content_type?: string
  storage_backend?: string
}

export interface KnowledgeDocument {
  id: string
  knowledge_base_id: string
  filename: string | null
  file_size: number | null
  mime_type: string | null
  status: string
  metadata: DocumentMetadata
  created_at: string
  updated_at: string
}

function basesUrl(workspaceId: string): string {
  return `/api/workspaces/${workspaceId}/knowledge-bases`
}

export async function listKnowledgeBases(workspaceId: string): Promise<KnowledgeBase[]> {
  const response = await apiClient.get<KnowledgeBase[]>(basesUrl(workspaceId))
  return response.data
}

export async function createKnowledgeBase(
  workspaceId: string,
  name: string,
  description: string
): Promise<KnowledgeBase> {
  const response = await apiClient.post<KnowledgeBase>(basesUrl(workspaceId), {
    name,
    description: description || null,
    type: 'document',
  })
  return response.data
}

export async function deleteKnowledgeBase(workspaceId: string, kbId: string): Promise<void> {
  await apiClient.delete(`${basesUrl(workspaceId)}/${kbId}`)
}

export async function listDocuments(
  workspaceId: string,
  kbId: string
): Promise<KnowledgeDocument[]> {
  const response = await apiClient.get<{ documents: KnowledgeDocument[]; total: number }>(
    `${basesUrl(workspaceId)}/${kbId}/documents`
  )
  return response.data.documents
}

export async function uploadDocument(
  workspaceId: string,
  kbId: string,
  file: File
): Promise<KnowledgeDocument> {
  const form = new FormData()
  form.append('file', file)
  const response = await apiClient.post<KnowledgeDocument>(
    `${basesUrl(workspaceId)}/${kbId}/documents`,
    form
  )
  return response.data
}

export async function deleteDocument(
  workspaceId: string,
  kbId: string,
  documentId: string
): Promise<void> {
  await apiClient.delete(`${basesUrl(workspaceId)}/${kbId}/documents/${documentId}`)
}

export async function downloadDocument(
  workspaceId: string,
  kbId: string,
  documentId: string,
  filename: string
): Promise<void> {
  // Fetched through the authenticated client rather than navigated to, because the
  // endpoint requires the bearer token and only this client can attach it.
  const response = await apiClient.get(
    `${basesUrl(workspaceId)}/${kbId}/documents/${documentId}/download`,
    { responseType: 'blob' }
  )
  const url = URL.createObjectURL(response.data as Blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
