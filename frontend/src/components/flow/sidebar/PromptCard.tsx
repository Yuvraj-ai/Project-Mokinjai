import { useState } from 'react'
import { Pencil, Trash2, Calendar } from 'lucide-react'
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
    <div className={`bg-white dark:bg-ink-800 rounded-xl border border-ink-100/80 dark:border-ink-700/60 p-4 flex flex-col transition-all duration-200 hover:border-accent-warm/40 hover:shadow-md ${deleting ? 'opacity-50 pointer-events-none' : ''}`}>
      <div className="flex items-start justify-between mb-2">
        <h3 className="text-sm font-body font-semibold text-ink-900 dark:text-cream-100 truncate pr-2">{prompt.name}</h3>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={(e) => { e.stopPropagation(); onEdit(prompt) }} className="p-1 rounded text-ink-300 hover:text-ink-600 dark:hover:text-cream-200 hover:bg-ink-50 dark:hover:bg-ink-700 transition-colors" title="Edit">
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button onClick={handleDelete} className="p-1 rounded text-ink-300 hover:text-status-error hover:bg-cream-100 dark:hover:bg-ink-700 transition-colors" title="Delete">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <div className="flex items-center gap-1.5 text-[10px] text-ink-300 dark:text-ink-400 mb-2">
        <Calendar className="w-3 h-3" />
        <span>{formatDate(prompt.created_at)}</span>
      </div>
      {prompt.description && (
        <p className="text-xs text-ink-400 dark:text-ink-300 line-clamp-3 leading-relaxed flex-1">{prompt.description}</p>
      )}
      {!prompt.description && (
        <p className="text-xs text-ink-300 dark:text-ink-400 italic flex-1">No description</p>
      )}
    </div>
  )
}
