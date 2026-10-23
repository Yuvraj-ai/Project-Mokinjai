import apiClient from './client'

export interface Folder {
  id: string
  name: string
  file_count: number
  created_at: string
}

export interface FileItem {
  id: string
  filename: string | null
  file_size: number | null
  mime_type: string | null
  folder_id: string | null
  attached_agent_count: number
  created_at: string
}

function filesUrl(workspaceId: string): string {
  return `/api/workspaces/${workspaceId}/files`
}

export async function listFolders(workspaceId: string): Promise<Folder[]> {
  const response = await apiClient.get<{ folders: Folder[]; total: number }>(
    `${filesUrl(workspaceId)}/folders`
  )
  return response.data.folders
}

export async function createFolder(workspaceId: string, name: string): Promise<Folder> {
  const response = await apiClient.post<Folder>(`${filesUrl(workspaceId)}/folders`, { name })
  return response.data
}

export async function renameFolder(
  workspaceId: string,
  folderId: string,
  name: string
): Promise<Folder> {
  const response = await apiClient.patch<Folder>(`${filesUrl(workspaceId)}/folders/${folderId}`, {
    name,
  })
  return response.data
}

export async function deleteFolder(
  workspaceId: string,
  folderId: string,
  opts?: { force?: boolean; confirm_name?: string }
): Promise<void> {
  await apiClient.delete(`${filesUrl(workspaceId)}/folders/${folderId}`, {
    params: opts?.force ? { force: true } : undefined,
    data: opts?.confirm_name !== undefined ? { confirm_name: opts.confirm_name } : undefined,
  })
}

export async function listDocuments(
  workspaceId: string,
  params?: { folder_id?: string; unfiled?: boolean; q?: string }
): Promise<{ documents: FileItem[]; total: number }> {
  const response = await apiClient.get<{ documents: FileItem[]; total: number }>(
    `${filesUrl(workspaceId)}/documents`,
    { params }
  )
  return response.data
}

export async function uploadDocument(
  workspaceId: string,
  file: File,
  folderId?: string | null
): Promise<FileItem> {
  const form = new FormData()
  form.append('file', file)
  if (folderId) form.append('folder_id', folderId)
  const response = await apiClient.post<FileItem>(`${filesUrl(workspaceId)}/documents`, form)
  return response.data
}

export async function moveDocuments(
  workspaceId: string,
  documentIds: string[],
  folderId: string | null
): Promise<number> {
  const response = await apiClient.patch<{ moved: number }>(
    `${filesUrl(workspaceId)}/documents`,
    { document_ids: documentIds, folder_id: folderId }
  )
  return response.data.moved
}

export async function deleteDocument(workspaceId: string, documentId: string): Promise<void> {
  await apiClient.delete(`${filesUrl(workspaceId)}/documents/${documentId}`)
}

export async function downloadDocument(
  workspaceId: string,
  documentId: string,
  filename: string
): Promise<void> {
  // Fetched through the authenticated client rather than navigated to, because the
  // endpoint requires the bearer token and only this client can attach it.
  const response = await apiClient.get(
    `${filesUrl(workspaceId)}/documents/${documentId}/download`,
    { responseType: 'blob' }
  )
  const url = URL.createObjectURL(response.data as Blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
