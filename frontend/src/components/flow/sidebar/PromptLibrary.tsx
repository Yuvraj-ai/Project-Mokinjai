import { useState, useEffect, useCallback } from 'react'
import { Plus, FileText } from 'lucide-react'
import { listPrompts, type PromptTemplate } from '../../../api/prompts'
import PromptCard from './PromptCard'
import PromptEditor from './PromptEditor'
import Button from '../../ui/Button'
import { Spinner, EmptyState } from '../../ui/Feedback'

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
        <Spinner />
      </div>
    )
  }

  if (fullPage) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-10">
        <div className="flex items-start justify-between mb-8 animate-fade-in-up stagger-1">
          <div>
            <h1 className="text-2xl font-semibold text-ink tracking-tight leading-tight">
              System Prompts
            </h1>
            <p className="mt-1 text-sm text-ink-muted">
              Create and manage reusable prompts for your AI agents
            </p>
          </div>
          <Button onClick={() => { setEditing(null); setShowEditor(true) }}>
            <Plus className="w-4 h-4" aria-hidden /> Create Prompt
          </Button>
        </div>

        {prompts.length === 0 ? (
          <div className="bg-surface border border-line rounded-xl animate-fade-in">
            <EmptyState
              icon={FileText}
              title="No prompts yet"
              description="Create your first system prompt to get started."
            />
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
      <div className="flex items-center justify-between px-4 py-3 border-b border-line">
        <h2 className="text-sm font-semibold text-ink">System Prompts</h2>
        <Button size="sm" variant="secondary" onClick={() => { setEditing(null); setShowEditor(true) }}>
          <Plus className="w-3.5 h-3.5" aria-hidden /> New Prompt
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {prompts.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No prompts yet"
            description="Create your first system prompt"
            className="py-10"
          />
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
