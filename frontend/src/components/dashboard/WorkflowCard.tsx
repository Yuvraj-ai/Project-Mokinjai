import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { deleteWorkflow } from '../../api/workflows'
import { Trash2, Clock, MoreVertical, Play, GitBranch } from 'lucide-react'

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
  index?: number
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return 'Unknown'
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function statusStyle(status?: string): { bg: string; color: string; dot: string } {
  switch (status?.toLowerCase()) {
    case 'active':
    case 'published':
      return { bg: 'rgba(34,197,94,0.1)', color: '#4ade80', dot: '#22c55e' }
    case 'running':
      return { bg: 'rgba(59,130,246,0.1)', color: '#60a5fa', dot: '#3b82f6' }
    case 'error':
    case 'failed':
      return { bg: 'rgba(239,68,68,0.1)', color: '#f87171', dot: '#ef4444' }
    default:
      return { bg: 'rgba(100,116,139,0.1)', color: 'var(--text-muted)', dot: 'var(--text-disabled)' }
  }
}

export default function WorkflowCard({ workflow, workspaceId, onDeleted, index = 0 }: WorkflowCardProps) {
  const navigate = useNavigate()
  const [deleting, setDeleting] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [hovered, setHovered] = useState(false)

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowMenu(false)
    const confirmed = window.confirm(`Delete "${workflow.name}"? This cannot be undone.`)
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

  const ss = statusStyle(workflow.status)

  return (
    <div
      onClick={() => navigate(`/workflows/${workflow.id}/edit`)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setShowMenu(false) }}
      className="relative rounded-xl cursor-pointer transition-all"
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${hovered ? 'var(--border-strong)' : 'var(--border-subtle)'}`,
        boxShadow: hovered ? 'var(--shadow-md)' : 'none',
        transform: hovered ? 'translateY(-2px)' : 'none',
        opacity: deleting ? 0.4 : 1,
        pointerEvents: deleting ? 'none' : 'auto',
        animationDelay: `${index * 60}ms`,
      }}
    >
      {/* Top accent bar */}
      <div
        className="h-0.5 rounded-t-xl"
        style={{
          background: `linear-gradient(90deg, var(--accent-from), var(--accent-to))`,
          opacity: hovered ? 1 : 0,
          transition: 'opacity 0.2s',
        }}
      />

      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{
                background: 'rgba(99,102,241,0.12)',
                border: '1px solid rgba(99,102,241,0.2)',
              }}
            >
              <GitBranch className="w-4 h-4" style={{ color: 'var(--accent-mid)' }} />
            </div>
            <h3
              className="text-sm font-semibold truncate"
              style={{ color: 'var(--text-primary)' }}
            >
              {workflow.name}
            </h3>
          </div>

          {/* Menu */}
          <div className="relative shrink-0 ml-2">
            <button
              onClick={(e) => { e.stopPropagation(); setShowMenu(!showMenu) }}
              className="p-1.5 rounded-lg transition-all"
              style={{
                color: 'var(--text-muted)',
                background: showMenu ? 'var(--bg-hover)' : 'transparent',
                opacity: hovered || showMenu ? 1 : 0,
              }}
            >
              <MoreVertical className="w-3.5 h-3.5" />
            </button>
            {showMenu && (
              <div
                className="absolute right-0 top-8 w-40 rounded-xl py-1 z-20 animate-fade-in glass-strong"
                style={{ boxShadow: 'var(--shadow-lg)' }}
              >
                <button
                  onClick={handleDelete}
                  className="w-full flex items-center gap-2 px-3 py-2.5 text-sm transition-colors"
                  style={{ color: '#f87171' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.08)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Delete workflow
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Status badge */}
        {workflow.status && (
          <div className="mb-3">
            <span
              className="inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide"
              style={{ background: ss.bg, color: ss.color }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: ss.dot }}
              />
              {workflow.status}
            </span>
          </div>
        )}

        {/* Description */}
        {workflow.description && (
          <p
            className="text-xs leading-relaxed mb-4 line-clamp-2"
            style={{ color: 'var(--text-muted)' }}
          >
            {workflow.description}
          </p>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between mt-3 pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
          <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-disabled)' }}>
            <Clock className="w-3 h-3" />
            <span>{formatDate(workflow.updated_at || workflow.created_at)}</span>
          </div>
          <div
            className="flex items-center gap-1 text-xs font-medium transition-opacity"
            style={{ color: 'var(--accent-mid)', opacity: hovered ? 1 : 0 }}
          >
            <Play className="w-3 h-3" fill="currentColor" />
            Open editor
          </div>
        </div>
      </div>
    </div>
  )
}
