import apiClient from './client'
import type { WebSearchMethod } from './agents'

export interface SearchCredential {
  provider: string
  has_key: boolean
}

/** The two hosted search providers. `native` needs no key. */
export const SEARCH_KEY_PROVIDERS: WebSearchMethod[] = ['tavily', 'exa']

export async function listSearchCredentials(
  workspaceId: string
): Promise<SearchCredential[]> {
  const response = await apiClient.get<SearchCredential[]>(
    `/api/workspaces/${workspaceId}/search-credentials`
  )
  return response.data
}

export async function saveSearchCredential(
  workspaceId: string,
  provider: WebSearchMethod,
  apiKey: string
): Promise<SearchCredential> {
  const response = await apiClient.put<SearchCredential>(
    `/api/workspaces/${workspaceId}/search-credentials/${provider}`,
    { api_key: apiKey }
  )
  return response.data
}

export async function deleteSearchCredential(
  workspaceId: string,
  provider: WebSearchMethod
): Promise<void> {
  await apiClient.delete(`/api/workspaces/${workspaceId}/search-credentials/${provider}`)
}
