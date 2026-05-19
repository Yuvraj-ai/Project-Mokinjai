import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { listWorkspaces, createWorkspace } from '../api/workspaces'
import { createWorkflow } from '../api/workflows'
import WorkflowList from '../components/dashboard/WorkflowList'
import { Plus, Loader2, Zap, GitBranch, Play } from 'lucide-react'

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

  useEffect(() => { initWorkspace() }, [initWorkspace])

  const handleCreateWorkflow = async () => {
    if (!workspaceId || creating) return
    setCreating(true)
    try {
      const workflow = await createWorkflow(workspaceId, {
        name: 'Untitled Workflow',
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
        <div className="flex flex-col items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, var(--accent-from), var(--accent-to))' }}
          >
            <Loader2 className="w-5 h-5 text-white animate-spin" />
          </div>
          <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading workspace…</span>
        </div>
      </div>
    )
  }

  return (
    <div
      className="max-w-6xl mx-auto px-6 py-8 animate-fade-in"
      style={{ color: 'var(--text-primary)' }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-2.5 mb-2">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.25)' }}
            >
              <GitBranch className="w-4 h-4" style={{ color: 'var(--accent-mid)' }} />
            </div>
            <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
              Workflows
            </h1>
          </div>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Build and orchestrate your AI agent pipelines
          </p>
        </div>

        <button
          id="create-workflow-btn"
          onClick={handleCreateWorkflow}
          disabled={creating}
          className="btn-primary"
        >
          {creating ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Plus className="w-4 h-4" />
          )}
          New Workflow
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { label: 'Total Workflows', icon: GitBranch, color: 'var(--accent-mid)', bg: 'rgba(99,102,241,0.1)' },
          { label: 'Executions Today', icon: Play, color: 'var(--status-success)', bg: 'rgba(34,197,94,0.1)' },
          { label: 'Agent Nodes Used', icon: Zap, color: 'var(--node-agent)', bg: 'rgba(168,85,247,0.1)' },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl p-4 flex items-center gap-3"
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div
              className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ background: stat.bg }}
            >
              <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
            </div>
            <div>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{stat.label}</p>
              <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>—</p>
            </div>
          </div>
        ))}
      </div>

      {/* Workflow list */}
      {workspaceId && (
        <WorkflowList
          workspaceId={workspaceId}
          key={refreshKey}
          onRefresh={() => setRefreshKey(k => k + 1)}
        />
      )}
    </div>
  )
}
