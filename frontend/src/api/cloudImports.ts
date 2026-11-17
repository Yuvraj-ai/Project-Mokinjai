import apiClient from './client'

export interface OneDriveItem {
  id: string
  name: string
  size: number | null
  mime_type: string | null
  is_folder: boolean
  child_count: number | null
}

export interface CloudConnection {
  provider: string
  account_label: string | null
  connected_at: string | null
}

export async function getConnectionStatus(): Promise<CloudConnection[]> {
  const response = await apiClient.get<CloudConnection[]>('/api/cloud-connections')
  return response.data
}

export async function getOneDriveAuthUrl(): Promise<string> {
  const response = await apiClient.get<{ url: string }>('/api/cloud-connections/onedrive/authorize')
  return response.data.url
}

export async function listOneDriveItems(itemId?: string): Promise<OneDriveItem[]> {
  const response = await apiClient.get<{ items: OneDriveItem[] }>(
    '/api/cloud-connections/onedrive/items',
    { params: itemId ? { item_id: itemId } : undefined }
  )
  return response.data.items
}

export async function importOneDriveItem(
  workspaceId: string,
  itemId: string
): Promise<{ document_id: string; filename: string; duplicate: boolean }> {
  // The id is the only thing sent: the server re-reads name, size and MIME from Graph.
  const response = await apiClient.post<{
    document_id: string
    filename: string
    duplicate: boolean
  }>(`/api/workspaces/${workspaceId}/imports/onedrive`, { item_id: itemId })
  return response.data
}

export async function importGoogleFile(
  workspaceId: string,
  fileId: string,
  accessToken: string
): Promise<{ document_id: string; filename: string; duplicate: boolean }> {
  // The token is used once and never stored; the server gates on Drive's metadata.
  const response = await apiClient.post<{
    document_id: string
    filename: string
    duplicate: boolean
  }>(`/api/workspaces/${workspaceId}/imports/google`, {
    file_id: fileId,
    access_token: accessToken,
  })
  return response.data
}
