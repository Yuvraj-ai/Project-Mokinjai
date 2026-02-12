export interface Position {
  x: number
  y: number
}

export interface FlowNode {
  id: string
  type: string
  position: Position
  data: Record<string, unknown>
}

export interface FlowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
}

export interface FlowDefinition {
  nodes: FlowNode[]
  edges: FlowEdge[]
}

export interface Workflow {
  id: string
  workspace_id: string
  name: string
  description: string
  flow_definition: FlowDefinition
  created_at: string
  updated_at: string
}

export interface WorkflowListResponse {
  workflows: Workflow[]
  total: number
}

export interface Workspace {
  id: string
  name: string
  owner_id: string
  created_at: string
  updated_at: string
}
