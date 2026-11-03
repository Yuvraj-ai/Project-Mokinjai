import apiClient from './client'

export interface AgentTemperature {
  supported: boolean
  minimum: number
  maximum: number
}

export interface AgentReasoning {
  supported: boolean
  levels: string[]
  default: string | null
}

export interface AgentAdvanced {
  top_p: boolean
  seed: boolean
  stop: boolean
}

/** Mirrors `agent_capabilities.Capabilities.as_dict()`. */
export interface AgentCapabilities {
  provider: string
  model_id: string
  max_output_tokens: number
  max_output_source: 'profile_override' | 'model_profile' | 'fallback'
  temperature: AgentTemperature
  reasoning: AgentReasoning
  advanced: AgentAdvanced
  native_web_search: boolean
  structured_output: boolean
  tool_calling: boolean
}

export interface AgentOption {
  id: string
  name: string
  description?: string | null
  provider?: string | null
  model_id?: string | null
  status?: string | null
  capabilities?: AgentCapabilities | null
  /** Skills only: the picker previews the `@`/`/` closure. */
  skill_refs?: string[] | null
  tool_refs?: string[] | null
}

export interface AgentOptions {
  llm_profiles: AgentOption[]
  structured_outputs: AgentOption[]
  skills: AgentOption[]
  connectors: AgentOption[]
  tools: AgentOption[]
  agents: AgentOption[]
}

export interface ResolvedSkill {
  id: string
  name: string
  root: boolean
}

export interface ResolvedTool {
  name: string
  source: 'builtin' | 'workspace'
  locked: boolean
  tool_id?: string | null
}

export interface ResolvedDependencies {
  skills: ResolvedSkill[]
  tools: ResolvedTool[]
}

export interface AgentParams {
  temperature?: number
  max_tokens?: number
  reasoning?: string
  streaming?: boolean
  top_p?: number
  seed?: number
  stop?: string[]
}

export type WebSearchMethod = 'tavily' | 'exa' | 'native'

export interface WebSearchSetting {
  enabled: boolean
  method: WebSearchMethod
}

/** Attach a folder but leave out specific files from it. */
export interface AgentFolderRule {
  id: string
  exclude_document_ids: string[]
}

/** Read shape: the server returns the resolved file set, not the write-time rules. */
export interface AgentDocumentItem {
  id: string
  filename: string | null
  folder_id: string | null
  source_folder_id: string | null
}

export interface AgentInput {
  name: string
  description: string | null
  llm_profile_id: string
  system_prompt: string
  source_prompt_id: string | null
  params: AgentParams
  structured_output_id: string | null
  web_search: WebSearchSetting | null
  skill_ids: string[]
  tool_ids: string[]
  folders: AgentFolderRule[]
  /** Loose file ids attached outside any folder rule. */
  documents: string[]
  /** Attached connections with their per-agent table allowlist (snapshot). */
  data_sources: AgentDataSourceRule[]
  connector_ids: string[]
  subagent_ids: string[]
}

export interface AgentDataSourceRule {
  id: string
  tables: string[]
}

export interface AgentDataSourceItem {
  id: string
  name: string
  tables: string[]
}

export type AgentStatus = 'ready' | 'needs_attention'

// The read `documents` is the resolved item list, which is why it cannot reuse the write-time `string[]`.
export interface Agent extends Omit<AgentInput, 'documents'> {
  id: string
  workspace_id: string
  resolved: ResolvedDependencies
  capabilities: AgentCapabilities | null
  status: AgentStatus
  issues: string[]
  documents: AgentDocumentItem[]
  data_sources: AgentDataSourceItem[]
  created_at: string
  updated_at: string
}

export interface AgentListItem {
  id: string
  name: string
  description: string | null
  llm_profile_id: string | null
  status: AgentStatus
  updated_at: string
}

/** Matches the server: 1–100, unique per workspace (case-insensitively). */
export const AGENT_NAME_MAX = 100
export const AGENT_DESCRIPTION_MAX = 2000
export const AGENT_PROMPT_MAX = 32000

export async function listAgents(workspaceId: string): Promise<AgentListItem[]> {
  const response = await apiClient.get<{ agents: AgentListItem[]; total: number }>(
    `/api/workspaces/${workspaceId}/agents`
  )
  return response.data.agents
}

export async function getAgent(workspaceId: string, agentId: string): Promise<Agent> {
  const response = await apiClient.get<Agent>(`/api/workspaces/${workspaceId}/agents/${agentId}`)
  return response.data
}

export async function getAgentOptions(
  workspaceId: string,
  agentId?: string
): Promise<AgentOptions> {
  const response = await apiClient.get<AgentOptions>(
    `/api/workspaces/${workspaceId}/agents/options`,
    { params: agentId ? { agent_id: agentId } : undefined }
  )
  return response.data
}

export async function createAgent(workspaceId: string, data: AgentInput): Promise<Agent> {
  const response = await apiClient.post<Agent>(`/api/workspaces/${workspaceId}/agents`, data)
  return response.data
}

export async function updateAgent(
  workspaceId: string,
  agentId: string,
  data: AgentInput
): Promise<Agent> {
  const response = await apiClient.put<Agent>(
    `/api/workspaces/${workspaceId}/agents/${agentId}`,
    data
  )
  return response.data
}

export async function deleteAgent(workspaceId: string, agentId: string): Promise<void> {
  await apiClient.delete(`/api/workspaces/${workspaceId}/agents/${agentId}`)
}

export interface FieldErrors {
  fields: Record<string, string>
  message: string | null
}

/**
 * A 422 from the agent API arrives as `detail: [{loc, msg}]`, because the field
 * the message belongs to is the useful part. Anything else is a plain message.
 */
export function fieldErrors(error: unknown): FieldErrors {
  const response = (error as { response?: { data?: { detail?: unknown } } })?.response
  const detail = response?.data?.detail
  if (typeof detail === 'string') return { fields: {}, message: detail }
  if (!Array.isArray(detail)) return { fields: {}, message: null }

  const fields: Record<string, string> = {}
  let message: string | null = null
  for (const item of detail) {
    const entry = item as { loc?: unknown; msg?: unknown }
    const loc = Array.isArray(entry.loc) ? entry.loc : []
    const field = loc.length > 0 ? String(loc[loc.length - 1]) : ''
    const text = typeof entry.msg === 'string' ? entry.msg : 'Invalid value'
    if (!field) message = message ?? text
    else if (!fields[field]) fields[field] = text
  }
  return { fields, message }
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export type AgentChatEvent =
  | { type: 'token'; delta: string }
  | { type: 'tool'; name: string; status: 'running' | 'done' }
  | { type: 'done'; execution_id: string; usage: Record<string, number>; cost_usd: number }
  | { type: 'error'; detail: string }

function parseEvent(raw: string): AgentChatEvent | null {
  let name = ''
  const dataLines: string[] = []
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) name = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!name || dataLines.length === 0) return null
  const payload = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
  if (name === 'token') return { type: 'token', delta: String(payload.delta ?? '') }
  if (name === 'tool') {
    return {
      type: 'tool',
      name: String(payload.name ?? ''),
      status: payload.status === 'done' ? 'done' : 'running',
    }
  }
  if (name === 'done') {
    return {
      type: 'done',
      execution_id: String(payload.execution_id ?? ''),
      usage: (payload.usage ?? {}) as Record<string, number>,
      cost_usd: Number(payload.cost_usd ?? 0),
    }
  }
  if (name === 'error') return { type: 'error', detail: String(payload.detail ?? '') }
  return null
}

/**
 * SSE over `fetch`: the turn's history is sent with every request, because the
 * backend keeps no conversation. Axios cannot read a stream, which is why the
 * chat path does not use the shared client.
 */
export async function* streamAgentChat(
  workspaceId: string,
  agentId: string,
  messages: ChatMessage[],
  signal?: AbortSignal
): AsyncGenerator<AgentChatEvent> {
  const base = import.meta.env.VITE_API_URL || ''
  const token = localStorage.getItem('access_token')
  const response = await fetch(
    `${base}/api/workspaces/${workspaceId}/agents/${agentId}/chat`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ messages }),
      signal,
    }
  )

  if (!response.ok || !response.body) {
    let detail = 'The chat could not be started.'
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // A non-JSON error body keeps the default message.
    }
    if (response.status === 401) window.location.href = '/login'
    throw new Error(detail)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const event = parseEvent(buffer.slice(0, boundary))
      buffer = buffer.slice(boundary + 2)
      if (event) yield event
      boundary = buffer.indexOf('\n\n')
    }
  }
}
