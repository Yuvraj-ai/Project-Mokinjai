import { useMutation, useQuery } from '@tanstack/react-query'
import { executeWorkflow, listExecutions, getExecution } from '../api/executions'
import { useExecutionStore } from '../store/executionStore'

export function useExecuteWorkflow(workspaceId: string, workflowId: string) {
  const { setExecution, setRunning, clearNodeStatuses } = useExecutionStore()

  return useMutation({
    mutationFn: (inputData: Record<string, any>) =>
      executeWorkflow(workspaceId, workflowId, inputData),
    onMutate: () => {
      clearNodeStatuses()
      setRunning(true)
    },
    onSuccess: (execution) => {
      setExecution(execution)
      setRunning(execution.status === 'running' || execution.status === 'pending')
    },
    onError: () => {
      setRunning(false)
    },
  })
}

export function useExecutions(workspaceId: string, params?: { workflow_id?: string }) {
  return useQuery({
    queryKey: ['executions', workspaceId, params],
    queryFn: () => listExecutions(workspaceId, params),
    enabled: !!workspaceId,
  })
}

export function useExecutionDetails(workspaceId: string, executionId: string) {
  return useQuery({
    queryKey: ['execution', workspaceId, executionId],
    queryFn: () => getExecution(workspaceId, executionId),
    enabled: !!workspaceId && !!executionId,
  })
}
