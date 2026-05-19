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
      setWorkflows(Array.isArray(data) ? data : data.items ?? data.workflows ?? [])
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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-indigo-600 animate-spin" />
        <span className="ml-3 text-sm text-gray-500">Loading workflows...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="text-red-500 text-sm">{error}</p>
        <button
          onClick={fetchWorkflows}
          className="mt-3 text-sm text-indigo-600 hover:text-indigo-500 font-medium"
        >
          Try again
        </button>
      </div>
    )
  }

  if (workflows.length === 0) {
    return (
      <div className="text-center py-20">
        <Inbox className="w-12 h-12 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-1">No workflows yet</h3>
        <p className="text-sm text-gray-500">Create your first workflow to get started.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
      {workflows.map((workflow) => (
        <WorkflowCard
          key={workflow.id}
          workflow={workflow}
          workspaceId={workspaceId}
          onDeleted={handleDeleted}
        />
      ))}
    </div>
  )
}
