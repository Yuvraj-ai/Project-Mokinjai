import apiClient from './client'

export type LlmProvider = 'openai' | 'anthropic' | 'gemini' | 'custom'

export interface LlmProfile {
  id: string
  workspace_id: string
  name: string
  provider: LlmProvider
  model_id: string
  base_url: string | null
  context_window: number
  compaction_at_tokens: number
  input_price_per_million: number
  output_price_per_million: number
  cache_price_per_million: number
  status: 'verified' | 'failed'
  last_error: string | null
  has_api_key: boolean
  usable: boolean
  created_at: string
  updated_at: string
}

export interface LlmProfileTestInput {
  name: string
  provider: LlmProvider
  model_id: string
  api_key?: string
  base_url?: string | null
  context_window?: number | null
  compaction_at_tokens?: number | null
  input_price_per_million: number
  output_price_per_million: number
  cache_price_per_million: number
  profile_id?: string | null
}

export async function listLlmProfiles(workspaceId: string): Promise<LlmProfile[]> {
  const response = await apiClient.get<{ profiles: LlmProfile[]; total: number }>(
    `/api/workspaces/${workspaceId}/llm-profiles`
  )
  return response.data.profiles
}

export async function lookupContextWindow(
  workspaceId: string,
  provider: LlmProvider,
  modelId: string
): Promise<{ known: boolean; max_input_tokens: number | null }> {
  const response = await apiClient.get(
    `/api/workspaces/${workspaceId}/llm-profiles/context-window`,
    { params: { provider, model_id: modelId } }
  )
  return response.data
}

export async function testLlmProfile(
  workspaceId: string,
  data: LlmProfileTestInput
): Promise<LlmProfile> {
  const response = await apiClient.post<LlmProfile>(
    `/api/workspaces/${workspaceId}/llm-profiles/test`,
    data
  )
  return response.data
}

export async function deleteLlmProfile(workspaceId: string, profileId: string): Promise<void> {
  await apiClient.delete(`/api/workspaces/${workspaceId}/llm-profiles/${profileId}`)
}
