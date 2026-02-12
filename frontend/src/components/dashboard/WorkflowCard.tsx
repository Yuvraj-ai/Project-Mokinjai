import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { deleteWorkflow } from '../../api/workflows'
import { Trash2, Clock, MoreVertical } from 'lucide-react'

interface Workflow {
  id: string
  name: string
  description?: string
  status?: string
  updated_at?: string
  created_at?: string
}

interface WorkflowCardProps {
  workflow: Workflow
  workspaceId: string
  onDeleted?: (id: string) => void
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return 'Unknown'
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function statusColor(status?: string): string {
  switch (status?.toLowerCase()) {
    case 'active':
    case 'published':
      return 'bg-green-100 text-green-700'
    case 'running':
      return 'bg-blue-100 text-blue-700'
    case 'error':
    case 'failed':
      return 'bg-red-100 text-red-700'
    default:
      return 'bg-gray-100 text-gray-600'
  }
}

export default function WorkflowCard({ workflow, workspaceId, onDeleted }: WorkflowCardProps) {
  const navigate = useNavigate()
  const [deleting, setDeleting] = useState(false)
  const [showMenu, setShowMenu] = useState(false)

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowMenu(false)
    const confirmed = window.confirm(`Delete "${workflow.name}"? This action cannot be undone.`)
    if (!confirmed) return

    setDeleting(true)
    try {
      await deleteWorkflow(workspaceId, workflow.id)
      onDeleted?.(workflow.id)
    } catch (err) {
      console.error('Failed to delete workflow:', err)
    } finally {
      setDeleting(false)
    }
  }

  const handleClick = () => {
    navigate(`/workflows/${workflow.id}/edit`)
  }

  return (
    <div
      onClick={handleClick}
      className={`relative bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md hover:border-indigo-200 transition-all cursor-pointer group ${
        deleting ? 'opacity-50 pointer-events-none' : ''
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <h3 className="text-base font-semibold text-gray-900 truncate pr-2">{workflow.name}</h3>
        <div className="relative shrink-0">
          <button
            onClick={(e) => {
              e.stopPropagation()
              setShowMenu(!showMenu)
            }}
            className="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <MoreVertical className="w-4 h-4" />
          </button>
          {showMenu && (
            <div className="absolute right-0 top-8 w-36 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10">
              <button
                onClick={handleDelete}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {workflow.status && (
        <span
          className={`inline-block text-xs font-medium px-2.5 py-0.5 rounded-full mb-3 ${statusColor(
            workflow.status
          )}`}
        >
          {workflow.status}
        </span>
      )}

      {workflow.description && (
        <p className="text-sm text-gray-500 line-clamp-2 mb-4">{workflow.description}</p>
      )}

      <div className="flex items-center gap-1.5 text-xs text-gray-400 mt-auto">
        <Clock className="w-3.5 h-3.5" />
        <span>Modified {formatDate(workflow.updated_at || workflow.created_at)}</span>
      </div>
    </div>
  )
}
