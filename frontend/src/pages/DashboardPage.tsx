import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { listWorkspaces, createWorkspace } from '../api/workspaces'
import { createWorkflow } from '../api/workflows'
import WorkflowList from '../components/dashboard/WorkflowList'
import Button from '../components/ui/Button'
import { Spinner } from '../components/ui/Feedback'
import { Plus } from 'lucide-react'

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
        <Spinner className="w-6 h-6" />
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="flex items-start justify-between mb-10 animate-fade-in-up stagger-1" data-od-id="dashboard-header">
        <div>
          <h1 className="text-2xl font-semibold text-ink tracking-tight leading-tight">
            Workflows
          </h1>
          <p className="text-ink-muted mt-1 text-sm max-w-md">
            Build and manage your AI agent workflows and pipelines.
          </p>
        </div>
        <Button onClick={handleCreateWorkflow} loading={creating}>
          <Plus className="w-4 h-4" aria-hidden />
          New Workflow
        </Button>
      </div>

      {workspaceId && (
        <div className="animate-fade-in-up stagger-2" data-od-id="workflows-grid">
          <WorkflowList workspaceId={workspaceId} key={refreshKey} />
        </div>
      )}
    </div>
  )
}
