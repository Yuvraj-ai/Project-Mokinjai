import { useState, useEffect, useCallback } from 'react'
import { listWorkflows } from '../../api/workflows'
import WorkflowCard from './WorkflowCard'
import { Loader2, Inbox, RefreshCw } from 'lucide-react'

interface Workflow {
  id: string
  name: string
  description?: string
  status?: string
  updated_at?: string
  created_at?: string
}

interface WorkflowListProps {
  workspaceId: string
  onRefresh?: () => void
}

export default function WorkflowList({ workspaceId }: WorkflowListProps) {
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchWorkflows = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listWorkflows(workspaceId, {})
      setWorkflows(Array.isArray(data) ? data : (data as any).workflows ?? [])
    } catch (err: any) {
      setError(err?.message || 'Failed to load workflows')
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => { fetchWorkflows() }, [fetchWorkflows])

  const handleDeleted = (deletedId: string) => {
    setWorkflows((prev) => prev.filter((w) => w.id !== deletedId))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-5 h-5 animate-spin mr-3" style={{ color: 'var(--accent-mid)' }} />
        <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading workflows…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-24">
        <p className="text-sm mb-3" style={{ color: '#f87171' }}>{error}</p>
        <button
          onClick={fetchWorkflows}
          className="btn-ghost text-sm"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Try again
        </button>
      </div>
    )
  }

  if (workflows.length === 0) {
    return (
      <div
        className="text-center py-24 rounded-2xl"
        style={{
          background: 'var(--bg-surface)',
          border: '1px dashed var(--border-default)',
        }}
      >
        <div
          className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)' }}
        >
          <Inbox className="w-7 h-7" style={{ color: 'var(--text-disabled)' }} />
        </div>
        <h3 className="text-base font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
          No workflows yet
        </h3>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Click "New Workflow" to build your first AI agent pipeline.
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {workflows.map((workflow, i) => (
        <WorkflowCard
          key={workflow.id}
          workflow={workflow}
          workspaceId={workspaceId}
          onDeleted={handleDeleted}
          index={i}
        />
      ))}
    </div>
  )
}
