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
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="flex items-end justify-between mb-10 animate-fade-in-up stagger-1">
        <div>
          <h1 className="text-3xl font-display text-ink-900 dark:text-cream-100 tracking-tight leading-none">
            Workflows
          </h1>
          <p className="text-ink-400 dark:text-ink-300 mt-2 text-sm font-body">
            Build and manage your AI agent workflows
          </p>
        </div>
        <button
          onClick={handleCreateWorkflow}
          disabled={creating}
          className="inline-flex items-center gap-2 bg-ink-800 dark:bg-cream-200 hover:bg-ink-900 dark:hover:bg-cream-300 disabled:bg-ink-400 text-cream-50 dark:text-ink-800 font-body font-medium py-2 px-5 rounded-lg text-sm transition-all duration-200 hover:shadow-md"
        >
          {creating ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Plus className="w-4 h-4" />
          )}
          New Workflow
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
