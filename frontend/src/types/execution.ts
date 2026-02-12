export interface NodeExecutionLog {
  node_id: string
  node_type: string
  status: string
  inputs?: Record<string, unknown> | null
  outputs?: Record<string, unknown> | null
  error?: string | null
  duration_ms?: number | null
  started_at?: string | null
  completed_at?: string | null
}

export interface Execution {
  id: string
  workflow_id: string | null
  workspace_id: string
  workflow_version?: number | null
  status: string
  trigger_type?: string | null
  input_data?: Record<string, unknown> | null
  output_data?: Record<string, unknown> | null
  error_message?: string | null
  execution_trace?: { nodes: NodeExecutionLog[] } | null
  execution_time_ms?: number | null
  token_usage?: { total_tokens?: number; prompt_tokens?: number; completion_tokens?: number } | null
  cost_usd?: number | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
}

export interface ExecutionListResponse {
  executions: Execution[]
  total: number
}
