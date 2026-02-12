import apiClient from './client'
import type { Workflow, WorkflowListResponse, FlowDefinition } from '../types/workflow'

export async function listWorkflows(
  workspaceId: string,
  params?: { page?: number; limit?: number; status?: string; search?: string }
): Promise<WorkflowListResponse> {
  const response = await apiClient.get<WorkflowListResponse>(
    `/api/workspaces/${workspaceId}/workflows`,
    { params }
  )
  return response.data
}

export async function getWorkflow(workspaceId: string, workflowId: string): Promise<Workflow> {
  const response = await apiClient.get<Workflow>(
    `/api/workspaces/${workspaceId}/workflows/${workflowId}`
  )
  return response.data
}

export async function createWorkflow(
  workspaceId: string,
  data: { name: string; description?: string }
): Promise<Workflow> {
  const response = await apiClient.post<Workflow>(
    `/api/workspaces/${workspaceId}/workflows`,
    data
  )
  return response.data
}

export async function updateWorkflow(
  workspaceId: string,
  workflowId: string,
  data: { name?: string; description?: string; flow_definition?: FlowDefinition }
): Promise<Workflow> {
  const response = await apiClient.put<Workflow>(
    `/api/workspaces/${workspaceId}/workflows/${workflowId}`,
    data
  )
  return response.data
}

export async function deleteWorkflow(workspaceId: string, workflowId: string): Promise<void> {
  await apiClient.delete(`/api/workspaces/${workspaceId}/workflows/${workflowId}`)
}
