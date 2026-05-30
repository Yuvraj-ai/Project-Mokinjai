import { useState, useEffect, useCallback } from 'react'
import { Plus, Loader2, FileText } from 'lucide-react'
import { listPrompts, type PromptTemplate } from '../../../api/prompts'
import PromptCard from './PromptCard'
import PromptEditor from './PromptEditor'

interface PromptLibraryProps {
  workspaceId: string
  fullPage?: boolean
}

export default function PromptLibrary({ workspaceId, fullPage }: PromptLibraryProps) {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<PromptTemplate | null>(null)
  const [showEditor, setShowEditor] = useState(false)

  const fetchPrompts = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listPrompts(workspaceId)
      setPrompts(data.prompts)
    } catch (err) {
      console.error('Failed to load prompts:', err)
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => { fetchPrompts() }, [fetchPrompts])

  const handleSaved = (saved: PromptTemplate) => {
    setPrompts((prev) => {
      const idx = prev.findIndex((p) => p.id === saved.id)
      if (idx >= 0) { const next = [...prev]; next[idx] = saved; return next }
      return [saved, ...prev]
    })
    setShowEditor(false)
    setEditing(null)
  }

  const handleDeleted = (id: string) => {
    setPrompts((prev) => prev.filter((p) => p.id !== id))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 text-accent animate-spin" />
      </div>
    )
  }

  if (fullPage) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-10">
        <div className="flex items-end justify-between mb-8 animate-fade-in-up stagger-1">
          <div>
            <h1 className="text-3xl font-display text-ink-900 dark:text-cream-100 tracking-tight leading-none">
              System Prompts
            </h1>
            <p className="text-ink-400 dark:text-ink-300 mt-2 text-sm font-body">
              Create and manage reusable prompts for your AI agents
            </p>
          </div>
          <button onClick={() => { setEditing(null); setShowEditor(true) }}
            className="inline-flex items-center gap-2 bg-ink-800 dark:bg-cream-200 hover:bg-ink-900 dark:hover:bg-cream-300 text-cream-50 dark:text-ink-800 font-body font-medium py-2 px-5 rounded-lg text-sm transition-all duration-200 hover:shadow-md">
            <Plus className="w-4 h-4" /> Create Prompt
          </button>
        </div>

        {prompts.length === 0 ? (
          <div className="text-center py-20 animate-fade-in">
            <FileText className="w-10 h-10 text-cream-300 dark:text-ink-600 mx-auto mb-4" strokeWidth={1.5} />
            <h3 className="text-2xl font-display italic text-ink-900 dark:text-cream-100 mb-2">No prompts yet</h3>
            <p className="text-sm text-ink-400 dark:text-ink-300 font-body">Create your first system prompt to get started.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {prompts.map((prompt, index) => (
              <div key={prompt.id} className={`animate-fade-in-up stagger-${Math.min(index + 1, 8)}`}>
                <PromptCard prompt={prompt} workspaceId={workspaceId}
                  onEdit={(p) => { setEditing(p); setShowEditor(true) }}
                  onDeleted={handleDeleted} />
              </div>
            ))}
          </div>
        )}

        {showEditor && (
          <PromptEditor workspaceId={workspaceId} prompt={editing}
            onClose={() => { setShowEditor(false); setEditing(null) }}
            onSaved={handleSaved} />
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-ink-100/60 dark:border-ink-700/60">
        <h2 className="text-xs font-body font-semibold text-ink-700 dark:text-cream-200">System Prompts</h2>
        <button onClick={() => { setEditing(null); setShowEditor(true) }}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-body font-medium bg-ink-800 dark:bg-cream-200 text-cream-50 dark:text-ink-800 rounded-md hover:bg-ink-900 dark:hover:bg-cream-300 transition-colors">
          <Plus className="w-3 h-3" /> New Prompt
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {prompts.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="w-8 h-8 text-ink-200 dark:text-ink-600 mx-auto mb-3" />
            <p className="text-xs text-ink-400 dark:text-ink-300 font-body">No prompts yet</p>
            <p className="text-[10px] text-ink-300 dark:text-ink-400 mt-1">Create your first system prompt</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2">
            {prompts.map((prompt) => (
              <div key={prompt.id} className="animate-fade-in">
                <PromptCard prompt={prompt} workspaceId={workspaceId}
                  onEdit={(p) => { setEditing(p); setShowEditor(true) }}
                  onDeleted={handleDeleted} />
              </div>
            ))}
          </div>
        )}
      </div>

      {showEditor && (
        <PromptEditor workspaceId={workspaceId} prompt={editing}
          onClose={() => { setShowEditor(false); setEditing(null) }}
          onSaved={handleSaved} />
      )}
    </div>
  )
}
