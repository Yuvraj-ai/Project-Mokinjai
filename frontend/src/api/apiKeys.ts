import apiClient from './client'

/**
 * API keys (the 2026-11-05 design): workspace-scoped keys with OpenRouter-
 * style budget controls. Plaintext appears exactly once, in create/rotate.
 */

export type ApiKeyStatus = 'active' | 'revoked' | 'disabled' | 'expired'
export type ResetPeriod = 'daily' | 'weekly' | 'monthly' | null

export interface ApiKeyRow {
  id: string
  workspace_id: string
  name: string
  prefix: string
  description: string | null
  status: ApiKeyStatus
  credit_limit_usd: string | null
  credit_reset_period: ResetPeriod
  spend_window_started_at: string | null
  created_at: string
  created_by: string
  expires_at: string | null
  last_used_at: string | null
}

export interface ApiKeyCreated extends ApiKeyRow {
  /** The plaintext — present only on create/rotate responses. */
  key: string
}

export interface DailySpend {
  date: string
  cost: number
}

export interface ApiKeyUsage {
  window_spend: number
  window_limit: number | null
  window_started_at: string | null
  totals: Record<'today' | 'week' | 'month' | 'total', number>
  daily: DailySpend[]
}

export interface KeyLogRow {
  id: string
  agent_id: string | null
  status: string
  trigger_type: string | null
  cost_usd: string | null
  execution_time_ms: number | null
  created_at: string
}

export async function listApiKeys(workspaceId: string): Promise<ApiKeyRow[]> {
  const response = await apiClient.get<ApiKeyRow[]>(
    `/api/workspaces/${workspaceId}/api-keys`
  )
  return response.data
}

export async function createApiKey(
  workspaceId: string,
  input: {
    name: string
    expires_at?: string | null
    credit_limit_usd?: string | null
    credit_reset_period?: ResetPeriod
    description?: string | null
  }
): Promise<ApiKeyCreated> {
  const response = await apiClient.post<ApiKeyCreated>(
    `/api/workspaces/${workspaceId}/api-keys`,
    input
  )
  return response.data
}

export async function getApiKey(workspaceId: string, keyId: string): Promise<ApiKeyRow> {
  const response = await apiClient.get<ApiKeyRow>(
    `/api/workspaces/${workspaceId}/api-keys/${keyId}`
  )
  return response.data
}

export async function updateApiKey(
  workspaceId: string,
  keyId: string,
  input: {
    name?: string
    credit_limit_usd?: string | null
    credit_reset_period?: ResetPeriod
    description?: string | null
  }
): Promise<ApiKeyRow> {
  const response = await apiClient.patch<ApiKeyRow>(
    `/api/workspaces/${workspaceId}/api-keys/${keyId}`,
    input
  )
  return response.data
}

export async function getApiKeyUsage(
  workspaceId: string,
  keyId: string
): Promise<ApiKeyUsage> {
  const response = await apiClient.get<ApiKeyUsage>(
    `/api/workspaces/${workspaceId}/api-keys/${keyId}/usage`
  )
  return response.data
}

export async function rotateApiKey(workspaceId: string, keyId: string): Promise<ApiKeyCreated> {
  const response = await apiClient.post<ApiKeyCreated>(
    `/api/workspaces/${workspaceId}/api-keys/${keyId}/rotate`
  )
  return response.data
}

export async function disableApiKey(workspaceId: string, keyId: string): Promise<ApiKeyRow> {
  const response = await apiClient.post<ApiKeyRow>(
    `/api/workspaces/${workspaceId}/api-keys/${keyId}/disable`
  )
  return response.data
}

export async function enableApiKey(workspaceId: string, keyId: string): Promise<ApiKeyRow> {
  const response = await apiClient.post<ApiKeyRow>(
    `/api/workspaces/${workspaceId}/api-keys/${keyId}/enable`
  )
  return response.data
}

export async function revokeApiKey(workspaceId: string, keyId: string): Promise<void> {
  await apiClient.delete(`/api/workspaces/${workspaceId}/api-keys/${keyId}`)
}

export async function getApiKeyLogs(
  workspaceId: string,
  keyId: string
): Promise<KeyLogRow[]> {
  // Per-key runs are executions; the executions router filters server-side.
  const response = await apiClient.get<{ executions: (KeyLogRow & Record<string, unknown>)[] }>(
    `/api/workspaces/${workspaceId}/executions?api_key_id=${keyId}&limit=100`
  )
  return response.data.executions as KeyLogRow[]
}
