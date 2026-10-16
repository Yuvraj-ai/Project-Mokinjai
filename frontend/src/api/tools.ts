import apiClient from './client'

export type ParameterType =
  | 'string'
  | 'integer'
  | 'number'
  | 'boolean'
  | 'array'
  | 'object'
  | 'null'
  | 'any'
export type ItemType = 'string' | 'integer' | 'number' | 'boolean' | 'object' | 'any'

export interface ToolParameter {
  name: string
  type: ParameterType
  description: string
  required: boolean
  items_type: ItemType | null
}

export interface ToolSchema {
  name: string
  description: string
  parameters: ToolParameter[]
  returns: ParameterType
  input_schema: Record<string, unknown>
}

export interface Tool {
  id: string
  workspace_id: string
  name: string
  description: string
  code: string
  parameters: ToolParameter[]
  returns: ParameterType
  input_schema: Record<string, unknown> | null
  category: 'custom'
  needs_sandbox: true
  created_at: string
  updated_at: string
}

export interface BuiltinTool {
  built_in_key: string
  name: string
  description: string
  category: 'built-in'
  needs_sandbox: false
}

export interface ToolValidation {
  valid: boolean
  errors: string[]
  schema: ToolSchema | null
}

export async function listTools(workspaceId: string): Promise<Tool[]> {
  const response = await apiClient.get<{ tools: Tool[]; total: number }>(
    `/api/workspaces/${workspaceId}/tools`
  )
  return response.data.tools
}

export async function listBuiltinTools(workspaceId: string): Promise<BuiltinTool[]> {
  const response = await apiClient.get<{ tools: BuiltinTool[]; total: number }>(
    `/api/workspaces/${workspaceId}/tools/builtin`
  )
  return response.data.tools
}

export async function validateTool(workspaceId: string, code: string): Promise<ToolValidation> {
  const response = await apiClient.post<ToolValidation>(
    `/api/workspaces/${workspaceId}/tools/validate`,
    { code }
  )
  return response.data
}

export async function createTool(workspaceId: string, code: string): Promise<Tool> {
  const response = await apiClient.post<Tool>(`/api/workspaces/${workspaceId}/tools`, { code })
  return response.data
}

export async function updateTool(workspaceId: string, toolId: string, code: string): Promise<Tool> {
  const response = await apiClient.put<Tool>(
    `/api/workspaces/${workspaceId}/tools/${toolId}`,
    { code }
  )
  return response.data
}

export async function deleteTool(workspaceId: string, toolId: string): Promise<void> {
  await apiClient.delete(`/api/workspaces/${workspaceId}/tools/${toolId}`)
}

/** How a parameter reads in a list row or a type chip. */
export function parameterTypeLabel(parameter: ToolParameter): string {
  if (parameter.type === 'array') {
    return parameter.items_type ? `list[${parameter.items_type}]` : 'list'
  }
  return parameter.type
}
