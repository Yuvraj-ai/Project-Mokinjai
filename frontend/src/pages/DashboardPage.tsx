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
        <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workflows</h1>
          <p className="text-gray-500 mt-1 text-sm">Build and manage your AI agent workflows</p>
        </div>
        <button
          onClick={handleCreateWorkflow}
          disabled={creating}
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium py-2.5 px-5 rounded-lg text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
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
        <WorkflowList workspaceId={workspaceId} key={refreshKey} />
      )}
    </div>
  )
}
