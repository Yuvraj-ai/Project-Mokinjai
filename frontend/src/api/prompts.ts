import apiClient from './client'

export interface PromptTemplate {
  id: string
  workspace_id: string
  name: string
  description?: string
  content: string
  created_at: string
  updated_at: string
}

export interface PromptListResponse {
  prompts: PromptTemplate[]
  total: number
}

export async function listPrompts(workspaceId: string): Promise<PromptListResponse> {
  const response = await apiClient.get<PromptListResponse>(
    `/api/workspaces/${workspaceId}/prompts`
  )
  return response.data
}

export async function getPrompt(workspaceId: string, promptId: string): Promise<PromptTemplate> {
  const response = await apiClient.get<PromptTemplate>(
    `/api/workspaces/${workspaceId}/prompts/${promptId}`
  )
  return response.data
}

export async function createPrompt(
  workspaceId: string,
  data: { name: string; description?: string; content: string }
): Promise<PromptTemplate> {
  const response = await apiClient.post<PromptTemplate>(
    `/api/workspaces/${workspaceId}/prompts`,
    data
  )
  return response.data
}

export async function updatePrompt(
  workspaceId: string,
  promptId: string,
  data: { name?: string; description?: string; content?: string }
): Promise<PromptTemplate> {
  const response = await apiClient.put<PromptTemplate>(
    `/api/workspaces/${workspaceId}/prompts/${promptId}`,
    data
  )
  return response.data
}

export async function deletePrompt(workspaceId: string, promptId: string): Promise<void> {
  await apiClient.delete(`/api/workspaces/${workspaceId}/prompts/${promptId}`)
}
