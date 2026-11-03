import { useState, useEffect, useCallback } from 'react'
import { listWorkflows } from '../../api/workflows'
import WorkflowCard from './WorkflowCard'
import { Spinner, EmptyState } from '../ui/Feedback'
import Button from '../ui/Button'
import { Inbox } from 'lucide-react'

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
        <Spinner />
        <span className="ml-3 text-sm text-ink-muted">Loading workflows...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-24">
        <p className="text-status-error text-sm">{error}</p>
        <Button variant="secondary" size="sm" className="mt-3" onClick={fetchWorkflows}>
          Try again
        </Button>
      </div>
    )
  }

  if (workflows.length === 0) {
    return (
      <div className="animate-fade-in">
        <EmptyState
          icon={Inbox}
          title="No workflows yet"
          description="Create your first workflow to get started."
        />
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-od-id="workflows-grid">
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
