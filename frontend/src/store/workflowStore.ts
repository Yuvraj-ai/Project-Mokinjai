import { create } from 'zustand'
import type { Node, Edge, OnNodesChange, OnEdgesChange, OnConnect } from '@xyflow/react'
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react'

export interface WorkflowMeta {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
}

interface WorkflowState {
  // Metadata
  workflowId: string | null
  workflowName: string
  workflowDescription: string

  // Flow state
  nodes: Node[]
  edges: Edge[]
  selectedNodeId: string | null
  isDirty: boolean

  // Actions - metadata
  setWorkflowMeta: (id: string, name: string, description: string) => void
  setWorkflowName: (name: string) => void
  setWorkflowDescription: (description: string) => void

  // Actions - flow manipulation
  setNodes: (nodes: Node[]) => void
  setEdges: (edges: Edge[]) => void
  onNodesChange: OnNodesChange
  onEdgesChange: OnEdgesChange
  onConnect: OnConnect
  addNode: (node: Node) => void
  updateNodeData: (nodeId: string, data: Record<string, unknown>) => void
  removeNode: (nodeId: string) => void

  // Actions - selection
  setSelectedNodeId: (nodeId: string | null) => void

  // Actions - dirty tracking
  markClean: () => void

  // Actions - reset
  resetWorkflow: () => void
}

const initialState = {
  workflowId: null,
  workflowName: 'Untitled Workflow',
  workflowDescription: '',
  nodes: [] as Node[],
  edges: [] as Edge[],
  selectedNodeId: null,
  isDirty: false,
}

export const useWorkflowStore = create<WorkflowState>()((set, get) => ({
  ...initialState,

  setWorkflowMeta: (id, name, description) =>
    set({
      workflowId: id,
      workflowName: name,
      workflowDescription: description,
      isDirty: false,
    }),

  setWorkflowName: (name) =>
    set({ workflowName: name, isDirty: true }),

  setWorkflowDescription: (description) =>
    set({ workflowDescription: description, isDirty: true }),

  setNodes: (nodes) =>
    set({ nodes, isDirty: true }),

  setEdges: (edges) =>
    set({ edges, isDirty: true }),

  onNodesChange: (changes) =>
    set({
      nodes: applyNodeChanges(changes, get().nodes),
      isDirty: true,
    }),

  onEdgesChange: (changes) =>
    set({
      edges: applyEdgeChanges(changes, get().edges),
      isDirty: true,
    }),

  onConnect: (connection) =>
    set({
      edges: addEdge(connection, get().edges),
      isDirty: true,
    }),

  addNode: (node) =>
    set({
      nodes: [...get().nodes, node],
      isDirty: true,
    }),

  updateNodeData: (nodeId, data) =>
    set({
      nodes: get().nodes.map((node) =>
        node.id === nodeId
          ? { ...node, data: { ...node.data, ...data } }
          : node,
      ),
      isDirty: true,
    }),

  removeNode: (nodeId) =>
    set({
      nodes: get().nodes.filter((n) => n.id !== nodeId),
      edges: get().edges.filter(
        (e) => e.source !== nodeId && e.target !== nodeId,
      ),
      selectedNodeId:
        get().selectedNodeId === nodeId ? null : get().selectedNodeId,
      isDirty: true,
    }),

  setSelectedNodeId: (nodeId) =>
    set({ selectedNodeId: nodeId }),

  markClean: () =>
    set({ isDirty: false }),

  resetWorkflow: () =>
    set({ ...initialState }),
}))

export default useWorkflowStore
