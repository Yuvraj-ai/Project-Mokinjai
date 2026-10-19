import { useCallback, useEffect, useMemo, useState } from 'react'
import { Bot, Loader2, MessageSquare, Plus, Settings2, Trash2 } from 'lucide-react'
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
import AgentChatPanel from '../components/agents/AgentChatPanel'
import AgentConfigDialog from '../components/agents/AgentConfigDialog'
import AgentCreateDialog from '../components/agents/AgentCreateDialog'

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
  const [chatAgent, setChatAgent] = useState<AgentListItem | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [banner, setBanner] = useState<string | null>(null)

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
      if (chatAgent?.id === item.id) setChatAgent(null)
    } catch (caught) {
      setBanner(fieldErrors(caught).message ?? 'Could not delete that agent.')
    }
  }

  if (loading || !workspaceId) {
    return (
      <div className="flex h-full items-center justify-center text-ink-400">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex h-full">
      <aside className="w-80 shrink-0 overflow-y-auto border-r border-ink-100/60 dark:border-ink-700/60 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h1 className="flex items-center gap-2 text-sm font-semibold text-ink-800 dark:text-cream-100">
            <Bot className="h-4 w-4" /> Agents
          </h1>
          <button
            type="button"
            disabled={busy}
            onClick={() => void openNew()}
            className="flex items-center gap-1 rounded-lg bg-accent-warm px-2 py-1 text-xs text-white disabled:opacity-50"
          >
            <Plus className="h-3 w-3" /> New
          </button>
        </div>

        {banner && (
          <p className="mb-3 rounded-lg bg-cream-100 dark:bg-ink-700/60 px-2 py-1.5 text-[11px] text-ink-600 dark:text-ink-200">
            {banner}
          </p>
        )}
        {error && (
          <p className="mb-3 rounded-lg border border-status-error/40 px-2 py-1.5 text-[11px] text-status-error">
            {error}
          </p>
        )}

        {groups.map(([letter, items]) => (
          <div key={letter} className="mb-3">
            <p className="mb-1 px-1 text-[10px] uppercase tracking-wider font-semibold text-ink-300">
              {letter}
            </p>
            <ul className="space-y-1">
              {items.map((item) => (
                <li
                  key={item.id}
                  className={`group rounded-lg px-2 py-1.5 ${
                    chatAgent?.id === item.id
                      ? 'bg-ink-800/5 dark:bg-ink-600/50'
                      : 'hover:bg-ink-50 dark:hover:bg-ink-700'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => void openExisting(item)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <span className="flex items-center gap-1.5">
                        <span className="truncate text-xs font-medium text-ink-700 dark:text-cream-100">
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
                        <span className="mt-0.5 block truncate text-[10px] text-ink-400">
                          {item.description}
                        </span>
                      )}
                    </button>
                    <div className="flex shrink-0 items-center gap-1 opacity-0 group-hover:opacity-100">
                      <button
                        type="button"
                        title="Configure"
                        onClick={() => void openExisting(item)}
                        className="text-ink-300 hover:text-ink-600"
                      >
                        <Settings2 className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        title="Chat"
                        onClick={() => setChatAgent(item)}
                        className="text-ink-300 hover:text-ink-600"
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        title="Delete"
                        onClick={() => void remove(item)}
                        className="text-ink-300 hover:text-status-error"
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
          <p className="px-1 text-[11px] text-ink-400">
            No agents yet. Create one to give a model a prompt, skills and tools.
          </p>
        )}
      </aside>

      <section className="flex-1 overflow-hidden">
        {chatAgent ? (
          <AgentChatPanel
            workspaceId={workspaceId}
            agentId={chatAgent.id}
            agentName={chatAgent.name}
            onClose={() => setChatAgent(null)}
          />
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center text-xs text-ink-400">
            Open an agent to configure it, or press the chat icon to test it.
          </div>
        )}
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
            if (chatAgent?.id === agentId) setChatAgent(null)
            void refresh(workspaceId)
          }}
        />
      )}
    </div>
  )
}
