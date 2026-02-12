import apiClient from './client'
import type { Execution, ExecutionListResponse } from '../types/execution'

export async function executeWorkflow(
  workspaceId: string,
  workflowId: string,
  inputData: Record<string, any> = {},
  asyncExecution = false
): Promise<Execution> {
  const response = await apiClient.post<Execution>(
    `/api/workspaces/${workspaceId}/workflows/${workflowId}/execute`,
    { input_data: inputData, async_execution: asyncExecution }
  )
  return response.data
}

export async function listExecutions(
  workspaceId: string,
  params?: { workflow_id?: string; status?: string; page?: number; limit?: number }
): Promise<ExecutionListResponse> {
  const response = await apiClient.get<ExecutionListResponse>(
    `/api/workspaces/${workspaceId}/executions`,
    { params }
  )
  return response.data
}

export async function getExecution(
  workspaceId: string,
  executionId: string
): Promise<Execution> {
  const response = await apiClient.get<Execution>(
    `/api/workspaces/${workspaceId}/executions/${executionId}`
  )
  return response.data
}
