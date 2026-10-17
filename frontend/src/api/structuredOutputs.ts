import apiClient from './client'

export type FieldType = 'string' | 'number' | 'integer' | 'boolean' | 'any' | 'list' | 'reference'
export type ItemType = 'string' | 'number' | 'integer' | 'boolean' | 'any' | 'reference'

export interface OutputField {
  name: string
  type: FieldType
  description: string
  required: boolean
  items_type?: ItemType | null
  items_ref?: string | null
  ref?: string | null
}

export interface StructuredOutput {
  id: string
  workspace_id: string
  name: string
  description: string
  fields: OutputField[]
  referenced_by: string[]
  compiled_schema: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface StructuredOutputInput {
  name: string
  description: string
  fields: OutputField[]
}

export interface ParsedSchema {
  fields: OutputField[]
  title: string | null
  description: string | null
}

export const SCALAR_TYPES: FieldType[] = ['string', 'number', 'integer', 'boolean', 'any']
export const ITEM_TYPES: ItemType[] = ['string', 'number', 'integer', 'boolean', 'any', 'reference']

export async function listStructuredOutputs(workspaceId: string): Promise<StructuredOutput[]> {
  const response = await apiClient.get<{ structured_outputs: StructuredOutput[]; total: number }>(
    `/api/workspaces/${workspaceId}/structured-outputs`
  )
  return response.data.structured_outputs
}

export async function getStructuredOutput(
  workspaceId: string,
  outputId: string
): Promise<StructuredOutput> {
  const response = await apiClient.get<StructuredOutput>(
    `/api/workspaces/${workspaceId}/structured-outputs/${outputId}`
  )
  return response.data
}

export async function createStructuredOutput(
  workspaceId: string,
  data: StructuredOutputInput
): Promise<StructuredOutput> {
  const response = await apiClient.post<StructuredOutput>(
    `/api/workspaces/${workspaceId}/structured-outputs`,
    data
  )
  return response.data
}

export async function updateStructuredOutput(
  workspaceId: string,
  outputId: string,
  data: StructuredOutputInput
): Promise<StructuredOutput> {
  const response = await apiClient.put<StructuredOutput>(
    `/api/workspaces/${workspaceId}/structured-outputs/${outputId}`,
    data
  )
  return response.data
}

export async function deleteStructuredOutput(
  workspaceId: string,
  outputId: string
): Promise<void> {
  await apiClient.delete(`/api/workspaces/${workspaceId}/structured-outputs/${outputId}`)
}

export async function parseSchema(workspaceId: string, schema: string): Promise<ParsedSchema> {
  const response = await apiClient.post<ParsedSchema>(
    `/api/workspaces/${workspaceId}/structured-outputs/parse-schema`,
    { schema }
  )
  return response.data
}

/** How a field reads in a list row or a type chip. */
export function fieldTypeLabel(field: OutputField): string {
  if (field.type === 'reference') return `@${field.ref}`
  if (field.type === 'list') {
    return field.items_type === 'reference' ? `list[@${field.items_ref}]` : `list[${field.items_type}]`
  }
  return field.type
}
