import apiClient from './client'

export type ConnectorTransport = 'streamable_http' | 'stdio'
export type ConnectorAuthType = 'none' | 'api_key' | 'connection_string' | 'oauth'
export type ConnectorStatus = 'pending' | 'enabled' | 'error'

export interface CatalogEntry {
  id: string
  display_name: string
  description: string
  transport: ConnectorTransport
  auth_type: ConnectorAuthType
  secret_label: string | null
  config_fields: string[]
  docs_url: string | null
}

export interface Connector {
  id: string
  workspace_id: string
  connector_type: string
  display_name: string
  name: string
  transport: string
  auth_type: string
  auth_scope: string
  status: ConnectorStatus
  has_auth: boolean
  config: Record<string, string>
  tools: string[]
  last_error: string | null
  last_tested_at: string | null
  created_at: string
  updated_at: string
}

// Never carries the ciphertext or the plaintext: the response model has no field for
// either, so a secret cannot leave the server through this client.
export interface ConnectorInput {
  connector_type: string
  name: string
  auth_secret: string
  config: Record<string, string>
}

export async function listCatalog(workspaceId: string): Promise<CatalogEntry[]> {
  const response = await apiClient.get<{ entries: CatalogEntry[]; total: number }>(
    `/api/workspaces/${workspaceId}/connectors/catalog`
  )
  return response.data.entries
}

export async function listConnectors(
  workspaceId: string,
  usable = false
): Promise<Connector[]> {
  const response = await apiClient.get<{ connectors: Connector[]; total: number }>(
    `/api/workspaces/${workspaceId}/connectors`,
    { params: usable ? { usable: true } : undefined }
  )
  return response.data.connectors
}

export async function createConnector(
  workspaceId: string,
  data: ConnectorInput
): Promise<Connector> {
  const response = await apiClient.post<Connector>(
    `/api/workspaces/${workspaceId}/connectors`,
    data
  )
  return response.data
}

export async function updateConnector(
  workspaceId: string,
  connectorId: string,
  data: Omit<ConnectorInput, 'connector_type'>
): Promise<Connector> {
  const response = await apiClient.put<Connector>(
    `/api/workspaces/${workspaceId}/connectors/${connectorId}`,
    data
  )
  return response.data
}

export async function testConnector(workspaceId: string, connectorId: string): Promise<Connector> {
  const response = await apiClient.post<Connector>(
    `/api/workspaces/${workspaceId}/connectors/${connectorId}/test`
  )
  return response.data
}

export async function deleteConnector(workspaceId: string, connectorId: string): Promise<void> {
  await apiClient.delete(`/api/workspaces/${workspaceId}/connectors/${connectorId}`)
}
