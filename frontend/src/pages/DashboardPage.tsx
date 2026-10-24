import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { listWorkspaces, createWorkspace } from '../api/workspaces'
import { createWorkflow } from '../api/workflows'
import WorkflowList from '../components/dashboard/WorkflowList'
import { Plus, Loader2 } from 'lucide-react'

export default function DashboardPage() {
  const navigate = useNavigate()
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const initWorkspace = useCallback(async () => {
    try {
      const workspaces = await listWorkspaces()
      if (workspaces && workspaces.length > 0) {
        setWorkspaceId(workspaces[0].id)
      } else {
        const newWs = await createWorkspace('My Workspace')
        setWorkspaceId(newWs.id)
      }
    } catch (err) {
      console.error('Failed to initialize workspace:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    initWorkspace()
  }, [initWorkspace])

  const handleCreateWorkflow = async () => {
    if (!workspaceId || creating) return
    setCreating(true)
    try {
      const workflow = await createWorkflow(workspaceId, {
        name: `Untitled Workflow`,
        description: '',
      })
      navigate(`/workflows/${workflow.id}/edit`)
    } catch (err) {
      console.error('Failed to create workflow:', err)
    } finally {
      setCreating(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-6 h-6 text-accent animate-spin" />
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-8 md:px-10 md:py-12">
      <div className="mb-10 flex flex-col gap-6 animate-fade-in-up stagger-1 md:flex-row md:items-end md:justify-between">
        <div className="max-w-xl">
          <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent-warm">
            <span className="size-2 rounded-full bg-accent-warm" />
            Workspace overview
          </div>
          <h1 className="text-4xl font-display leading-none tracking-tight text-ink-900 dark:text-cream-100 md:text-5xl">
            Build once. Run everywhere.
          </h1>
          <p className="mt-4 max-w-lg text-sm leading-6 text-ink-400 dark:text-ink-300 md:text-base">
            Orchestrate prompts, tools, models, and knowledge into reliable AI workflows.
          </p>
        </div>
        <button
          onClick={handleCreateWorkflow}
          disabled={creating}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-ink-800 px-5 text-sm font-semibold text-cream-50 shadow-lg shadow-ink-900/10 transition-all duration-200 hover:-translate-y-0.5 hover:bg-ink-900 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-60 dark:bg-cream-100 dark:text-ink-900 dark:hover:bg-white"
        >
          {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          New workflow
        </button>
      </div>

      {workspaceId && (
        <div className="animate-fade-in-up stagger-2">
          <WorkflowList workspaceId={workspaceId} key={refreshKey} />
        </div>
      )}
    </div>
  )
}
