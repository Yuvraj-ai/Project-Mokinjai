import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bot, MessagesSquare, Plus, Settings2, Trash2 } from 'lucide-react'
import { listWorkspaces } from '../api/workspaces'
import {
  deleteAgent,
  fieldErrors,
  getAgent,
  getAgentOptions,
  listAgents,
  type Agent,
  type AgentListItem,
  type AgentOptions,
} from '../api/agents'
import AgentConfigDialog from '../components/agents/AgentConfigDialog'
import AgentCreateDialog from '../components/agents/AgentCreateDialog'
import Button from '../components/ui/Button'
import { Spinner } from '../components/ui/Feedback'

interface Draft {
  agent: Agent | null
  name: string
  description: string
}

export default function AgentsPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [agents, setAgents] = useState<AgentListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [options, setOptions] = useState<AgentOptions | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [banner, setBanner] = useState<string | null>(null)
  const navigate = useNavigate()

  const refresh = useCallback(async (id: string) => {
    setAgents(await listAgents(id))
  }, [])

  useEffect(() => {
    listWorkspaces()
      .then(async (workspaces) => {
        if (!workspaces?.length) return
        const id = workspaces[0].id
        setWorkspaceId(id)
        setAgents(await listAgents(id))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const groups = useMemo(() => {
    const byLetter = new Map<string, AgentListItem[]>()
    for (const agent of [...agents].sort((a, b) => a.name.localeCompare(b.name))) {
      const letter = (agent.name[0] ?? '#').toUpperCase()
      byLetter.set(letter, [...(byLetter.get(letter) ?? []), agent])
    }
    return [...byLetter.entries()]
  }, [agents])

  const openNew = () => {
    setError(null)
    setBanner(null)
    setCreating(true)
  }

  const startDraft = async (name: string, description: string) => {
    if (!workspaceId) return
    setCreating(false)
    setBusy(true)
    setError(null)
    try {
      setOptions(await getAgentOptions(workspaceId))
      setDraft({ agent: null, name, description })
    } catch {
      setError('Could not load the agent options.')
    } finally {
      setBusy(false)
    }
  }

  const openExisting = async (item: AgentListItem) => {
    if (!workspaceId) return
    setError(null)
    setBanner(null)
    setBusy(true)
    try {
      const [agent, loaded] = await Promise.all([
        getAgent(workspaceId, item.id),
        getAgentOptions(workspaceId, item.id),
      ])
      setOptions(loaded)
      setDraft({ agent, name: agent.name, description: agent.description ?? '' })
    } catch {
      setError('Could not load that agent.')
    } finally {
      setBusy(false)
    }
  }

  const closeDraft = () => setDraft(null)

  const remove = async (item: AgentListItem) => {
    if (!workspaceId) return
    if (!window.confirm(`Delete “${item.name}”? This cannot be undone.`)) return
    setError(null)
    setBanner(null)
    try {
      await deleteAgent(workspaceId, item.id)
      await refresh(workspaceId)
    } catch (caught) {
      setBanner(fieldErrors(caught).message ?? 'Could not delete that agent.')
    }
  }

  if (loading || !workspaceId) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    )
  }

  return (
    <div className="flex h-full">
      <aside className="w-80 shrink-0 overflow-y-auto border-r border-line bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <h1 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Bot className="h-4 w-4" /> Agents
          </h1>
          <Button size="sm" disabled={busy} onClick={() => void openNew()}>
            <Plus className="h-3.5 w-3.5" /> New
          </Button>
        </div>

        {banner && (
          <p className="mb-3 rounded-lg bg-surface-muted px-2.5 py-1.5 text-xs text-ink-muted">
            {banner}
          </p>
        )}
        {error && (
          <p className="mb-3 rounded-lg bg-status-error-soft px-2.5 py-1.5 text-xs text-status-error">
            {error}
          </p>
        )}

        {groups.map(([letter, items]) => (
          <div key={letter} className="mb-3">
            <p className="mb-1 px-1 font-mono text-[10px] uppercase tracking-wider text-ink-subtle">
              {letter}
            </p>
            <ul className="space-y-0.5">
              {items.map((item) => (
                <li
                  key={item.id}
                  className={`group rounded-lg px-2 py-1.5 transition-colors duration-150 ${
                    'hover:bg-surface-muted'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => void openExisting(item)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <span className="flex items-center gap-1.5">
                        <span className="truncate text-xs font-medium text-ink">
                          {item.name}
                        </span>
                        <span
                          className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                            item.status === 'ready' ? 'bg-status-success' : 'bg-status-warning'
                          }`}
                          title={item.status === 'ready' ? 'Ready' : 'Needs attention'}
                        />
                      </span>
                      {item.description && (
                        <span className="mt-0.5 block truncate text-[11px] text-ink-subtle">
                          {item.description}
                        </span>
                      )}
                    </button>
                    <div className="flex shrink-0 items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                      <button
                        type="button"
                        title="Configure"
                        onClick={() => void openExisting(item)}
                        className="rounded p-1 text-ink-subtle hover:bg-surface-muted hover:text-ink"
                      >
                        <Settings2 className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        title="Chat in the Playground"
                        onClick={() => navigate(`/playground?agent=${item.id}`)}
                        className="rounded p-1 text-ink-subtle hover:bg-surface-muted hover:text-ink"
                      >
                        <MessagesSquare className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        title="Delete"
                        onClick={() => void remove(item)}
                        className="rounded p-1 text-ink-subtle hover:bg-status-error-soft hover:text-status-error"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}

        {agents.length === 0 && (
          <p className="px-1 text-xs text-ink-subtle">
            No agents yet. Create one to give a model a prompt, skills and tools.
          </p>
        )}
      </aside>

      <section className="flex-1 overflow-hidden">
        <div className="flex h-full items-center justify-center px-6 text-center text-sm text-ink-subtle">
          Open an agent to configure it, or press the chat icon to run it in the Playground.
        </div>
      </section>

      {creating && (
        <AgentCreateDialog
          onClose={() => setCreating(false)}
          onContinue={(name, description) => void startDraft(name, description)}
        />
      )}

      {draft && options && (
        <AgentConfigDialog
          workspaceId={workspaceId}
          options={options}
          agent={draft.agent}
          initialName={draft.name}
          initialDescription={draft.description}
          onClose={closeDraft}
          onSaved={(saved) => {
            setDraft({ agent: saved, name: saved.name, description: saved.description ?? '' })
            void refresh(workspaceId)
            void getAgentOptions(workspaceId, saved.id).then(setOptions).catch(() => {})
          }}
          onDeleted={(agentId) => {
            setDraft(null)
            void refresh(workspaceId)
          }}
        />
      )}
    </div>
  )
}
