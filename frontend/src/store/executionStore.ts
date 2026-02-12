import { create } from 'zustand'
import type { Execution } from '../types/execution'

export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

export interface NodeExecutionStatus {
  nodeId: string
  status: NodeStatus
  output?: unknown
  error?: string
}

interface ExecutionState {
  currentExecution: Execution | null
  isRunning: boolean
  nodeStatuses: Record<string, NodeExecutionStatus>

  // Used by useExecution hooks and ExecutionPanel/ExecutionHistoryPage
  setExecution: (execution: Execution | null) => void
  setRunning: (running: boolean) => void
  clearNodeStatuses: () => void
  setNodeStatus: (nodeId: string, status: NodeExecutionStatus) => void

  // Used by useWebSocket
  updateExecution: (updates: Partial<Execution>) => void
  updateNodeStatus: (nodeId: string, status: NodeExecutionStatus) => void
  completeExecution: (output?: Record<string, unknown>, error?: string) => void
}

export const useExecutionStore = create<ExecutionState>()((set, get) => ({
  currentExecution: null,
  isRunning: false,
  nodeStatuses: {},

  setExecution: (execution) =>
    set({
      currentExecution: execution,
      isRunning: execution
        ? execution.status === 'running' || execution.status === 'pending'
        : false,
    }),

  setRunning: (running) => set({ isRunning: running }),

  clearNodeStatuses: () => set({ nodeStatuses: {} }),

  setNodeStatus: (nodeId, status) =>
    set({
      nodeStatuses: {
        ...get().nodeStatuses,
        [nodeId]: status,
      },
    }),

  updateExecution: (updates) => {
    const current = get().currentExecution
    if (!current) return
    set({
      currentExecution: { ...current, ...updates },
      isRunning: updates.status
        ? updates.status === 'running' || updates.status === 'pending'
        : get().isRunning,
    })
  },

  updateNodeStatus: (nodeId, status) =>
    set({
      nodeStatuses: {
        ...get().nodeStatuses,
        [nodeId]: status,
      },
    }),

  completeExecution: (output, error) => {
    const current = get().currentExecution
    if (!current) return
    set({
      currentExecution: {
        ...current,
        status: error ? 'failed' : 'completed',
        output_data: output ?? current.output_data,
        error_message: error ?? current.error_message,
        completed_at: new Date().toISOString(),
      },
      isRunning: false,
    })
  },
}))
