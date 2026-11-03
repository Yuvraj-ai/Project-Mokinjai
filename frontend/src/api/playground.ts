import apiClient from './client'

/**
 * Playground chat: server-owned sessions. The client sends only the new
 * message; history is loaded from the backend and replayed as it streamed.
 */

export interface PlaygroundSession {
  id: string
  workspace_id: string
  agent_id: string
  title: string
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface ActivityEvent {
  type: 'tool_start' | 'tool_end' | 'files_staged'
  id?: string
  name?: string
  kind?: 'sql' | 'code' | 'skill' | 'mcp' | 'web' | 'subagent' | 'tool'
  args?: unknown
  result?: unknown
  duration_ms?: number | null
  names?: string[]
}

export interface PlaygroundMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  reasoning: string | null
  activity: ActivityEvent[] | null
  structured: Record<string, unknown> | null
  status: 'completed' | 'stopped' | 'failed' | null
  usage: { input_tokens?: number; output_tokens?: number; total_tokens?: number } | null
  cost_usd: number | null
  execution_id: string | null
  created_at: string
}

export interface PlaygroundSessionDetail {
  session: PlaygroundSession
  messages: PlaygroundMessage[]
}

export type PlaygroundEvent =
  | { type: 'message'; user_message_id: string; assistant_message_id: string }
  | { type: 'token'; delta: string }
  | { type: 'reasoning'; delta: string }
  | { type: 'activity'; payload: ActivityEvent }
  | { type: 'done'; usage: PlaygroundMessage['usage']; cost_usd: number; status: string }
  | { type: 'error'; detail: string }

export async function listSessions(workspaceId: string, agentId?: string): Promise<PlaygroundSession[]> {
  const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : ''
  const response = await apiClient.get<{ sessions: PlaygroundSession[]; total: number }>(
    `/api/workspaces/${workspaceId}/playground/sessions${query}`
  )
  return response.data.sessions
}

export async function createSession(workspaceId: string, agentId: string): Promise<PlaygroundSession> {
  const response = await apiClient.post<PlaygroundSession>(
    `/api/workspaces/${workspaceId}/playground/sessions`,
    { agent_id: agentId }
  )
  return response.data
}

export async function getSession(
  workspaceId: string,
  sessionId: string
): Promise<PlaygroundSessionDetail> {
  const response = await apiClient.get<PlaygroundSession & { messages: PlaygroundMessage[] }>(
    `/api/workspaces/${workspaceId}/playground/sessions/${sessionId}`
  )
  const { messages, ...session } = response.data
  return { session, messages: messages ?? [] }
}

export async function renameSession(
  workspaceId: string,
  sessionId: string,
  title: string
): Promise<PlaygroundSession> {
  const response = await apiClient.patch<PlaygroundSession>(
    `/api/workspaces/${workspaceId}/playground/sessions/${sessionId}`,
    { title }
  )
  return response.data
}

export async function deleteSession(workspaceId: string, sessionId: string): Promise<void> {
  await apiClient.delete(`/api/workspaces/${workspaceId}/playground/sessions/${sessionId}`)
}

interface RawSseEvent {
  event: string
  data: Record<string, unknown>
}

function parseEvent(block: string): RawSseEvent | null {
  let event = ''
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) event = line.slice(7).trim()
    else if (line.startsWith('data: ')) data += line.slice(6)
  }
  if (!event) return null
  try {
    return { event, data: JSON.parse(data) as Record<string, unknown> }
  } catch {
    return null
  }
}

/**
 * SSE over `fetch` — Axios cannot read a stream. The body carries only the
 * new message content; the backend owns the history.
 */
export async function* streamSessionChat(
  workspaceId: string,
  sessionId: string,
  content: string,
  signal?: AbortSignal
): AsyncGenerator<PlaygroundEvent> {
  const base = import.meta.env.VITE_API_URL || ''
  const token = localStorage.getItem('access_token')
  const response = await fetch(
    `${base}/api/workspaces/${workspaceId}/playground/sessions/${sessionId}/chat`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content }),
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
      if (!event) continue
      const d = event.data
      if (event.event === 'message')
        yield {
          type: 'message',
          user_message_id: String(d.user_message_id),
          assistant_message_id: String(d.assistant_message_id),
        }
      else if (event.event === 'token') yield { type: 'token', delta: String(d.delta ?? '') }
      else if (event.event === 'reasoning')
        yield { type: 'reasoning', delta: String(d.delta ?? '') }
      else if (event.event === 'activity')
        yield { type: 'activity', payload: d as unknown as ActivityEvent }
      else if (event.event === 'done')
        yield {
          type: 'done',
          usage: d.usage as PlaygroundMessage['usage'],
          cost_usd: Number(d.cost_usd ?? 0),
          status: String(d.status ?? 'completed'),
        }
      else if (event.event === 'error')
        yield { type: 'error', detail: String(d.detail ?? 'The turn failed.') }
      boundary = buffer.indexOf('\n\n')
    }
  }
}
