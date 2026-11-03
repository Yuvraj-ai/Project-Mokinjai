import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { deleteWorkflow, updateWorkflow } from '../../api/workflows'
import { Trash2, Clock, MoreVertical, Pencil, Check, X } from 'lucide-react'
import Badge, { type BadgeTone } from '../ui/Badge'
import Menu, { MenuItem } from '../ui/Menu'
import { cn } from '../../lib/utils'

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

function statusTone(status?: string): BadgeTone {
  switch (status?.toLowerCase()) {
    case 'active':
    case 'published':
      return 'success'
    case 'running':
      return 'info'
    case 'error':
    case 'failed':
      return 'danger'
    default:
      return 'neutral'
  }
}

export default function WorkflowCard({ workflow, workspaceId, onDeleted, onRenamed }: WorkflowCardProps) {
  const navigate = useNavigate()
  const [deleting, setDeleting] = useState(false)
  const [editing, setEditing] = useState(false)
  const [nameValue, setNameValue] = useState(workflow.name)

  const handleDelete = async () => {
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
      className={cn(
        'relative bg-surface rounded-xl border border-line p-5 h-full flex flex-col',
        'hover:border-line-strong transition-colors duration-150 cursor-pointer group animate-fade-in-up',
        deleting && 'opacity-50 pointer-events-none',
      )}
      data-od-id={`workflow-card-${workflow.id.slice(0, 8)}`}
    >
      <div className="flex items-start justify-between mb-3 gap-2">
        {editing ? (
          <div className="flex items-center gap-1 flex-1 min-w-0" onClick={(e) => e.stopPropagation()}>
            <input
              type="text"
              value={nameValue}
              onChange={(e) => setNameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRename()
                if (e.key === 'Escape') { setEditing(false); setNameValue(workflow.name) }
              }}
              onBlur={handleRename}
              autoFocus
              className="flex-1 min-w-0 text-sm font-medium text-ink bg-surface border border-line rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <button onClick={handleRename} aria-label="Save name" className="p-1 text-status-success hover:bg-status-success-soft rounded">
              <Check className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => { setEditing(false); setNameValue(workflow.name) }} aria-label="Cancel rename" className="p-1 text-ink-subtle hover:bg-surface-muted rounded">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <h3 className="text-[15px] font-semibold text-ink truncate leading-snug pt-0.5">
            {workflow.name}
          </h3>
        )}
        <div className="shrink-0" onClick={(e) => e.stopPropagation()}>
          <Menu
            trigger={
              <button
                aria-label="Workflow actions"
                className="p-1.5 rounded-md text-ink-subtle hover:text-ink hover:bg-surface-muted opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity duration-150"
                data-od-id={`workflow-menu-${workflow.id.slice(0, 8)}`}
              >
                <MoreVertical className="w-4 h-4" />
              </button>
            }
          >
            <MenuItem icon={Pencil} onClick={() => setEditing(true)}>
              Rename
            </MenuItem>
            <MenuItem icon={Trash2} destructive onClick={handleDelete}>
              Delete
            </MenuItem>
          </Menu>
        </div>
      </div>

      {workflow.status && (
        <div className="mb-4">
          <Badge tone={statusTone(workflow.status)} dot>
            {workflow.status}
          </Badge>
        </div>
      )}

      {workflow.description && (
        <p className="text-[13px] text-ink-muted line-clamp-2 leading-relaxed mb-4">
          {workflow.description}
        </p>
      )}

      <div className="flex items-center gap-1.5 text-xs text-ink-subtle mt-auto font-mono">
        <Clock className="w-3.5 h-3.5" aria-hidden />
        <span>Modified {formatDate(workflow.updated_at || workflow.created_at)}</span>
      </div>
    </div>
  )
}
