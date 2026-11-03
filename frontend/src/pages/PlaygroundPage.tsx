import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listAgents, type AgentListItem } from '../api/agents'
import { listWorkspaces } from '../api/workspaces'
import {
  createSession,
  deleteSession,
  getSession,
  listSessions,
  renameSession,
  type PlaygroundMessage,
  type PlaygroundSession,
} from '../api/playground'
import AgentPane from '../components/playground/AgentPane'
import SessionPane from '../components/playground/SessionPane'
import ThreadPane from '../components/playground/ThreadPane'

export default function PlaygroundPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [agents, setAgents] = useState<AgentListItem[]>([])
  const [sessions, setSessions] = useState<PlaygroundSession[]>([])
  const [messages, setMessages] = useState<PlaygroundMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const agentId = searchParams.get('agent')
  const sessionId = searchParams.get('session')

  useEffect(() => {
    listWorkspaces()
      .then((workspaces) => {
        if (workspaces.length > 0) setWorkspaceId(workspaces[0].id)
      })
      .catch(() => setError('Could not load workspaces.'))
  }, [])

  useEffect(() => {
    if (!workspaceId) return
    listAgents(workspaceId)
      .then((rows) => {
        setAgents(rows)
        setLoading(false)
        if (rows.length > 0 && !searchParams.get('agent')) {
          setSearchParams({ agent: rows[0].id }, { replace: true })
        }
      })
      .catch(() => {
        setError('Could not load agents.')
        setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId])

  const refreshSessions = useCallback(
    (targetAgent: string) => {
      if (!workspaceId) return
      listSessions(workspaceId, targetAgent)
        .then(setSessions)
        .catch(() => setError('Could not load sessions.'))
    },
    [workspaceId]
  )

  useEffect(() => {
    if (workspaceId && agentId) refreshSessions(agentId)
  }, [workspaceId, agentId, refreshSessions])

  useEffect(() => {
    if (!workspaceId || !sessionId) {
      setMessages([])
      return
    }
    setBusy(true)
    getSession(workspaceId, sessionId)
      .then((detail) => setMessages(detail.messages))
      .catch(() => setError('Could not load the session.'))
      .finally(() => setBusy(false))
  }, [workspaceId, sessionId])

  const selectedAgent = agents.find((agent) => agent.id === agentId) ?? null
  const activeSession = sessions.find((session) => session.id === sessionId) ?? null

  const handleTurnEnded = useCallback(() => {
    if (workspaceId && agentId) refreshSessions(agentId)
    if (workspaceId && sessionId) {
      getSession(workspaceId, sessionId)
        .then((detail) => setMessages(detail.messages))
        .catch(() => {})
    }
  }, [workspaceId, agentId, sessionId, refreshSessions])

  const handleCreate = async () => {
    if (!workspaceId || !agentId) return
    setBusy(true)
    setError(null)
    try {
      const session = await createSession(workspaceId, agentId)
      setSessions((current) => [session, ...current])
      setSearchParams({ agent: agentId, session: session.id })
    } catch {
      setError('Could not create the session.')
    } finally {
      setBusy(false)
    }
  }

  const handleRename = async (id: string, title: string) => {
    if (!workspaceId) return
    try {
      const updated = await renameSession(workspaceId, id, title)
      setSessions((current) =>
        current.map((session) => (session.id === id ? updated : session))
      )
    } catch {
      setError('Could not rename the session.')
    }
  }

  const handleDelete = async (id: string) => {
    if (!workspaceId) return
    try {
      await deleteSession(workspaceId, id)
      setSessions((current) => current.filter((session) => session.id !== id))
      if (sessionId === id) setSearchParams({ agent: agentId ?? '' })
    } catch {
      setError('Could not delete the session.')
    }
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-[13px] text-ink-subtle">
        Loading…
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0">
      <AgentPane
        agents={agents}
        selectedId={agentId}
        onSelect={(id) => setSearchParams({ agent: id })}
      />
      <SessionPane
        agentName={selectedAgent?.name ?? ''}
        sessions={sessions}
        selectedId={sessionId}
        busy={busy}
        onSelect={(id) => agentId && setSearchParams({ agent: agentId, session: id })}
        onCreate={() => void handleCreate()}
        onRename={(id, title) => void handleRename(id, title)}
        onDelete={(id) => void handleDelete(id)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        {error && (
          <p className="rounded-lg bg-status-error-soft px-3 py-2 m-3 text-[13px] text-status-error">
            {error}
          </p>
        )}
        <ThreadPane
          workspaceId={workspaceId}
          session={activeSession}
          messages={messages}
          onTurnEnded={handleTurnEnded}
        />
      </div>
    </div>
  )
}
