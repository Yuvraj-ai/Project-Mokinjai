import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { deleteWorkflow, updateWorkflow } from '../../api/workflows'
import { Trash2, Clock, MoreVertical, Pencil, Check, X } from 'lucide-react'

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
  onRenamed?: (id: string, name: string) => void
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
      return 'bg-status-success/10 text-status-success'
    case 'running':
      return 'bg-status-info/10 text-status-info'
    case 'error':
    case 'failed':
      return 'bg-status-error/10 text-status-error'
    default:
      return 'bg-cream-200 text-ink-400'
  }
}

export default function WorkflowCard({ workflow, workspaceId, onDeleted, onRenamed }: WorkflowCardProps) {
  const navigate = useNavigate()
  const [deleting, setDeleting] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [editing, setEditing] = useState(false)
  const [nameValue, setNameValue] = useState(workflow.name)

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

  const handleRename = async () => {
    const trimmed = nameValue.trim()
    if (!trimmed || trimmed === workflow.name) {
      setEditing(false)
      setNameValue(workflow.name)
      return
    }
    try {
      await updateWorkflow(workspaceId, workflow.id, { name: trimmed })
      onRenamed?.(workflow.id, trimmed)
    } catch (err) {
      console.error('Failed to rename workflow:', err)
      setNameValue(workflow.name)
    }
    setEditing(false)
  }

  const handleClick = () => {
    navigate(`/workflows/${workflow.id}/edit`)
  }

  return (
    <div
      onClick={handleClick}
      className={`relative bg-white dark:bg-ink-800 rounded-xl border border-ink-100/80 dark:border-ink-700/60 p-5 shadow-sm hover:border-accent-warm/40 hover:shadow-md transition-all duration-200 cursor-pointer group animate-fade-in-up ${
        deleting ? 'opacity-50 pointer-events-none' : ''
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        {editing ? (
          <div className="flex items-center gap-1 flex-1 min-w-0" onClick={(e) => e.stopPropagation()}>
            <input
              type="text"
              value={nameValue}
              onChange={(e) => setNameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRename();
                if (e.key === 'Escape') { setEditing(false); setNameValue(workflow.name); }
              }}
              onBlur={handleRename}
              autoFocus
              className="flex-1 text-base font-body font-semibold text-ink-900 bg-ink-50 border border-ink-200 rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-accent-warm/40"
            />
            <button onClick={handleRename} className="p-0.5 text-status-success hover:bg-status-success/10 rounded">
              <Check className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => { setEditing(false); setNameValue(workflow.name); }} className="p-0.5 text-ink-300 hover:bg-ink-50 rounded">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <h3 className="text-base font-body font-semibold text-ink-900 dark:text-cream-100 truncate pr-2 leading-snug">
            {workflow.name}
          </h3>
        )}
        <div className="relative shrink-0">
          <button
            onClick={(e) => {
              e.stopPropagation()
              setShowMenu(!showMenu)
            }}
            className="p-1 rounded-md text-ink-300 hover:text-ink-600 hover:bg-cream-100 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
          >
            <MoreVertical className="w-4 h-4" />
          </button>
          {showMenu && (
            <div className="absolute right-0 top-8 w-36 bg-white dark:bg-ink-800 rounded-lg shadow-lg border border-ink-100/60 dark:border-ink-700/60 py-1 z-10 animate-scale-in">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setShowMenu(false)
                  setEditing(true)
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink-600 dark:text-ink-300 hover:bg-cream-100 dark:hover:bg-ink-700 transition-colors duration-150"
              >
                <Pencil className="w-4 h-4" />
                Rename
              </button>
              <button
                onClick={handleDelete}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-status-error hover:bg-cream-100 transition-colors duration-150"
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
          className={`inline-block text-xs font-medium px-2.5 py-0.5 rounded-full mb-4 font-body ${statusColor(
            workflow.status
          )}`}
        >
          {workflow.status}
        </span>
      )}

      {workflow.description && (
        <p className="text-sm text-ink-400 dark:text-ink-300 line-clamp-2 mb-5 font-body leading-relaxed">
          {workflow.description}
        </p>
      )}

      <div className="flex items-center gap-1.5 text-xs text-ink-300 dark:text-ink-400 mt-auto font-body">
        <Clock className="w-3.5 h-3.5" />
        <span>Modified {formatDate(workflow.updated_at || workflow.created_at)}</span>
      </div>
    </div>
  )
}
