import apiClient from './client'

export type ExternalDatabaseKind = 'postgres' | 'mysql' | 'mongodb' | 'chromadb'

// Mirrors the backend's KINDS. `kind` is a label and a validation hint — the backend
// refuses a record whose kind and target fields disagree — not a driver selector.
export const EXTERNAL_DATABASE_KINDS: ExternalDatabaseKind[] = [
  'postgres',
  'mysql',
  'mongodb',
  'chromadb',
]

export interface ExternalDatabase {
  id: string
  workspace_id: string
  name: string
  kind: ExternalDatabaseKind
  database_name: string | null
  collection_name: string | null
  has_uri: boolean
  created_at: string
  updated_at: string
}

export interface ExternalDatabaseInput {
  name: string
  kind: ExternalDatabaseKind
  uri: string
  database_name?: string | null
  collection_name?: string | null
}

function databasesUrl(workspaceId: string): string {
  return `/api/workspaces/${workspaceId}/external-databases`
}

export async function listExternalDatabases(
  workspaceId: string
): Promise<ExternalDatabase[]> {
  const response = await apiClient.get<{ connections: ExternalDatabase[]; total: number }>(
    databasesUrl(workspaceId)
  )
  return response.data.connections
}

export async function createExternalDatabase(
  workspaceId: string,
  data: ExternalDatabaseInput
): Promise<ExternalDatabase> {
  const response = await apiClient.post<ExternalDatabase>(databasesUrl(workspaceId), data)
  return response.data
}

export async function deleteExternalDatabase(
  workspaceId: string,
  connectionId: string
): Promise<void> {
  await apiClient.delete(`${databasesUrl(workspaceId)}/${connectionId}`)
}

export interface ConnectionColumnSchema {
  name: string
  type: string
  nullable: boolean
}

export interface ConnectionTableSchema {
  schema: string
  name: string
  columns: ConnectionColumnSchema[]
}

export interface ConnectionSchema {
  tables: ConnectionTableSchema[]
  fetched_at: string
}

export async function getConnectionSchema(
  workspaceId: string,
  connectionId: string
): Promise<ConnectionSchema> {
  const response = await apiClient.get<ConnectionSchema>(
    `${databasesUrl(workspaceId)}/${connectionId}/schema`
  )
  return response.data
}
