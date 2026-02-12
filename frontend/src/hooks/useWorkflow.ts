import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listWorkflows, getWorkflow, createWorkflow, updateWorkflow, deleteWorkflow } from '../api/workflows'
import type { FlowDefinition } from '../types/workflow'

export function useWorkflows(workspaceId: string, params?: { page?: number; search?: string }) {
  return useQuery({
    queryKey: ['workflows', workspaceId, params],
    queryFn: () => listWorkflows(workspaceId, params),
    enabled: !!workspaceId,
  })
}

export function useWorkflow(workspaceId: string, workflowId: string) {
  return useQuery({
    queryKey: ['workflow', workspaceId, workflowId],
    queryFn: () => getWorkflow(workspaceId, workflowId),
    enabled: !!workspaceId && !!workflowId,
  })
}

export function useCreateWorkflow(workspaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      createWorkflow(workspaceId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows', workspaceId] })
    },
  })
}

export function useUpdateWorkflow(workspaceId: string, workflowId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { name?: string; description?: string; flow_definition?: FlowDefinition }) =>
      updateWorkflow(workspaceId, workflowId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', workspaceId, workflowId] })
      queryClient.invalidateQueries({ queryKey: ['workflows', workspaceId] })
    },
  })
}

export function useDeleteWorkflow(workspaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (workflowId: string) => deleteWorkflow(workspaceId, workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows', workspaceId] })
    },
  })
}
