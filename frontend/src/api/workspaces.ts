import apiClient from './client'
import type { Workspace } from '../types/workflow'

export async function listWorkspaces(): Promise<Workspace[]> {
  const response = await apiClient.get<Workspace[]>('/api/workspaces')
  return response.data
}

export async function createWorkspace(name: string): Promise<Workspace> {
  const response = await apiClient.post<Workspace>('/api/workspaces', { name })
  return response.data
}
