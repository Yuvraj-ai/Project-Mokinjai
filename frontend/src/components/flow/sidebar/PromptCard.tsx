import { useState } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { deletePrompt, type PromptTemplate } from '../../../api/prompts'

interface PromptCardProps {
  prompt: PromptTemplate
  workspaceId: string
  onEdit: (prompt: PromptTemplate) => void
  onDeleted: (id: string) => void
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export default function PromptCard({ prompt, workspaceId, onEdit, onDeleted }: PromptCardProps) {
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    const confirmed = window.confirm(`Delete "${prompt.name}"? This cannot be undone.`)
    if (!confirmed) return
    setDeleting(true)
    try {
      await deletePrompt(workspaceId, prompt.id)
      onDeleted(prompt.id)
    } catch (err) {
      console.error('Failed to delete prompt:', err)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className={`bg-surface rounded-xl border border-line p-4 flex flex-col h-full transition-colors duration-150 hover:border-line-strong ${deleting ? 'opacity-50 pointer-events-none' : ''}`}>
      <div className="flex items-start justify-between mb-2">
        <h3 className="text-sm font-semibold text-ink truncate pr-2">{prompt.name}</h3>
        <div className="flex items-center gap-0.5 shrink-0">
          <button onClick={(e) => { e.stopPropagation(); onEdit(prompt) }} aria-label="Edit" className="p-1 rounded-md text-ink-subtle hover:text-ink hover:bg-surface-muted transition-colors">
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button onClick={handleDelete} aria-label="Delete" className="p-1 rounded-md text-ink-subtle hover:bg-status-error-soft hover:text-status-error transition-colors">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <div className="flex items-center gap-1.5 font-mono text-[11px] text-ink-subtle mb-2">
        <span>{formatDate(prompt.created_at)}</span>
        <span aria-hidden="true">·</span>
        <span title="Exact count from tiktoken (o200k_base), measured server-side">
          {prompt.token_count.toLocaleString()} tokens
        </span>
      </div>
      {prompt.description && (
        <p className="text-xs text-ink-muted line-clamp-3 leading-relaxed flex-1">{prompt.description}</p>
      )}
      {!prompt.description && (
        <p className="text-xs text-ink-subtle italic flex-1">No description</p>
      )}
    </div>
  )
}
