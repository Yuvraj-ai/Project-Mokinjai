import { useState, useEffect, useCallback } from 'react'
import { listWorkflows } from '../../api/workflows'
import WorkflowCard from './WorkflowCard'
import { Loader2, Inbox } from 'lucide-react'

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
      setWorkflows(Array.isArray(data) ? data : (data as any).items ?? data.workflows ?? [])
    } catch (err: any) {
      setError(err?.message || 'Failed to load workflows')
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => {
    fetchWorkflows()
  }, [fetchWorkflows])

  const handleDeleted = (deletedId: string) => {
    setWorkflows((prev) => prev.filter((w) => w.id !== deletedId))
  }

  const handleRenamed = (renamedId: string, newName: string) => {
    setWorkflows((prev) => prev.map((w) => w.id === renamedId ? { ...w, name: newName } : w))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-5 h-5 text-accent animate-spin" />
        <span className="ml-3 text-sm text-ink-300 font-body">Loading workflows...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-24">
        <p className="text-status-error text-sm font-body">{error}</p>
        <button
          onClick={fetchWorkflows}
          className="mt-3 text-sm text-accent hover:text-accent-warm font-body font-medium transition-colors duration-300"
        >
          Try again
        </button>
      </div>
    )
  }

  if (workflows.length === 0) {
    return (
      <div className="text-center py-24 animate-fade-in">
        <Inbox className="w-10 h-10 text-cream-300 mx-auto mb-5" strokeWidth={1.5} />
        <h3 className="text-2xl font-display italic text-ink-900 dark:text-cream-100 mb-2">No workflows yet</h3>
        <p className="text-sm text-ink-400 dark:text-ink-300 font-body">
          Create your first workflow to get started.
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
      {workflows.map((workflow, index) => (
        <div
          key={workflow.id}
          className={`animate-fade-in-up stagger-${Math.min(index + 1, 8)}`}
        >
          <WorkflowCard
            workflow={workflow}
            workspaceId={workspaceId}
            onDeleted={handleDeleted}
            onRenamed={handleRenamed}
          />
        </div>
      ))}
    </div>
  )
}
