import { useCallback, useEffect, useMemo, useState } from 'react'
import { Bot, Plus } from 'lucide-react'
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
import AgentCard from '../components/agents/AgentCard'
import AgentConfigDialog from '../components/agents/AgentConfigDialog'
import AgentCreateDialog from '../components/agents/AgentCreateDialog'
import Button from '../components/ui/Button'
import { Spinner, EmptyState, Callout } from '../components/ui/Feedback'

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

  const refresh = useCallback(async (id: string) => {
    setAgents(await listAgents(id))
  }, [])

  useEffect(() => {
    listWorkspaces()
      .then(async (workspaces) => {
        if (!workspaces?.length) return
        const id = workspaces[0].id
        setWorkspaceId(id)
        const [loadedAgents, loadedOptions] = await Promise.all([
          listAgents(id),
          getAgentOptions(id).catch(() => null),
        ])
        setAgents(loadedAgents)
        if (loadedOptions) setOptions(loadedOptions)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const llmProfileMap = useMemo(() => {
    const map = new Map<string, string>()
    if (options?.llm_profiles) {
      for (const p of options.llm_profiles) {
        map.set(p.id, p.name)
      }
    }
    return map
  }, [options])

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
      const loaded = options ?? (await getAgentOptions(workspaceId))
      setOptions(loaded)
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
    if (!window.confirm(`Delete "${item.name}"? This cannot be undone.`)) return
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
        <Spinner className="w-6 h-6" />
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-8 py-10">
        <div className="flex items-start justify-between mb-8 animate-fade-in-up stagger-1">
          <div>
            <h1 className="text-2xl font-semibold text-ink tracking-tight leading-tight flex items-center gap-2.5">
              <Bot className="w-6 h-6" aria-hidden />
              Agents
              <span className="font-mono text-xs font-normal text-ink-subtle ml-1">
                {agents.length}
              </span>
            </h1>
            <p className="mt-1 text-sm text-ink-muted">
              Configure autonomous AI agents with specialized prompts, skills, and tools.
            </p>
          </div>
          <Button disabled={busy} onClick={() => void openNew()}>
            <Plus className="w-4 h-4" aria-hidden /> New Agent
          </Button>
        </div>

        {banner && (
          <div className="mb-6 animate-fade-in">
            <Callout tone="danger">{banner}</Callout>
          </div>
        )}
        {error && (
          <div className="mb-6 animate-fade-in">
            <Callout tone="danger">{error}</Callout>
          </div>
        )}

        {agents.length === 0 ? (
          <div className="bg-surface border border-line rounded-xl animate-fade-in">
            <EmptyState
              icon={Bot}
              title="No agents yet"
              description="Create an agent to give a model a prompt, skills, and tools."
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent, index) => (
              <div
                key={agent.id}
                className={`animate-fade-in-up stagger-${Math.min(index + 1, 8)}`}
              >
                <AgentCard
                  agent={agent}
                  llmProfileName={agent.llm_profile_id ? llmProfileMap.get(agent.llm_profile_id) : undefined}
                  onClick={() => void openExisting(agent)}
                  onDelete={() => void remove(agent)}
                />
              </div>
            ))}
          </div>
        )}

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
            onDeleted={() => {
              setDraft(null)
              void refresh(workspaceId)
            }}
          />
        )}
      </div>
    </div>
  )
}

