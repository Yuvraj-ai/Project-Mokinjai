import { useState, useEffect, useCallback, useRef } from 'react'
import { X, GripVertical } from 'lucide-react'
import { createPrompt, updatePrompt, type PromptTemplate } from '../../../api/prompts'

interface PromptEditorProps {
  workspaceId: string
  prompt: PromptTemplate | null
  onClose: () => void
  onSaved: (prompt: PromptTemplate) => void
}

interface Variable {
  name: string
  compulsory: boolean
}

function detectVariables(content: string): string[] {
  const regex = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g
  const vars: string[] = []
  let match
  while ((match = regex.exec(content)) !== null) {
    if (!vars.includes(match[1])) {
      vars.push(match[1])
    }
  }
  return vars
}

function estimateTokens(content: string): number {
  const words = content.split(/\s+/).filter(Boolean).length
  return Math.ceil(words / 0.75)
}

export default function PromptEditor({ workspaceId, prompt, onClose, onSaved }: PromptEditorProps) {
  const [name, setName] = useState(prompt?.name || '')
  const [description, setDescription] = useState(prompt?.description || '')
  const [content, setContent] = useState(prompt?.content || '')
  const [variables, setVariables] = useState<Variable[]>([])
  const [saving, setSaving] = useState(false)
  const [size, setSize] = useState({ width: 500, height: 600 })
  const dragRef = useRef<{ startX: number; startY: number; startW: number; startH: number } | null>(null)

  useEffect(() => {
    const detected = detectVariables(content)
    setVariables((prev) => {
      const existing = new Map(prev.map((v) => [v.name, v.compulsory]))
      return detected.map((name) => ({
        name,
        compulsory: existing.get(name) ?? false,
      }))
    })
  }, [content])

  const handleSave = async () => {
    if (!name.trim() || !content.trim()) return
    setSaving(true)
    try {
      let saved: PromptTemplate
      if (prompt) {
        saved = await updatePrompt(workspaceId, prompt.id, { name: name.trim(), description: description.trim() || undefined, content })
      } else {
        saved = await createPrompt(workspaceId, { name: name.trim(), description: description.trim() || undefined, content })
      }
      onSaved(saved)
    } catch (err) {
      console.error('Failed to save prompt:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragRef.current = { startX: e.clientX, startY: e.clientY, startW: size.width, startH: size.height }
    const handleDrag = (ev: MouseEvent) => {
      if (!dragRef.current) return
      const dx = ev.clientX - dragRef.current.startX
      const dy = ev.clientY - dragRef.current.startY
      setSize({
        width: Math.max(400, dragRef.current.startW + dx),
        height: Math.max(400, dragRef.current.startH + dy),
      })
    }
    const handleUp = () => {
      dragRef.current = null
      document.removeEventListener('mousemove', handleDrag)
      document.removeEventListener('mouseup', handleUp)
    }
    document.addEventListener('mousemove', handleDrag)
    document.addEventListener('mouseup', handleUp)
  }, [size])

  const toggleCompulsory = (varName: string) => {
    setVariables((prev) => prev.map((v) => v.name === varName ? { ...v, compulsory: !v.compulsory } : v))
  }

  const removeVariable = (varName: string) => {
    const regex = new RegExp(`\\{${varName}\\}`, 'g')
    setContent((prev) => prev.replace(regex, ''))
  }

  const tokenCount = estimateTokens(content)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative bg-white dark:bg-ink-800 rounded-xl shadow-2xl border border-ink-100/60 dark:border-ink-700/60 flex flex-col overflow-hidden"
        style={{ width: size.width, height: size.height }}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-ink-100/60 dark:border-ink-700/60">
          <h2 className="text-sm font-body font-semibold text-ink-800 dark:text-cream-100">{prompt ? 'Edit Prompt' : 'New Prompt'}</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-ink-50 dark:hover:bg-ink-700 text-ink-400 transition-colors"><X className="w-4 h-4" /></button>
        </div>

        <div className="flex-1 overflow-auto p-4 space-y-3">
          <div>
            <label className="block text-[10px] font-semibold text-ink-300 dark:text-ink-400 uppercase tracking-wider mb-1">Name</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Prompt name"
              className="w-full text-sm font-body border border-ink-100/60 dark:border-ink-600 rounded-lg px-3 py-2 bg-ink-50/30 dark:bg-ink-700/50 text-ink-700 dark:text-cream-200 placeholder-ink-300 focus:outline-none focus:ring-1 focus:ring-accent-warm/40 focus:border-accent-warm transition-all" />
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-ink-300 dark:text-ink-400 uppercase tracking-wider mb-1">Description</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Brief description..." rows={2}
              className="w-full text-xs font-body border border-ink-100/60 dark:border-ink-600 rounded-lg px-3 py-2 bg-ink-50/30 dark:bg-ink-700/50 text-ink-700 dark:text-cream-200 placeholder-ink-300 focus:outline-none focus:ring-1 focus:ring-accent-warm/40 focus:border-accent-warm resize-none transition-all" />
          </div>
          <div className="flex-1">
            <label className="block text-[10px] font-semibold text-ink-300 dark:text-ink-400 uppercase tracking-wider mb-1">System Prompt</label>
            <textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="Write your system prompt here. Use {variable_name} for variables..."
              className="w-full text-xs font-mono border border-ink-100/60 dark:border-ink-600 rounded-lg px-3 py-2 bg-ink-50/30 dark:bg-ink-700/50 text-ink-700 dark:text-cream-200 placeholder-ink-300 focus:outline-none focus:ring-1 focus:ring-accent-warm/40 focus:border-accent-warm resize-none transition-all"
              style={{ minHeight: 200 }} />
          </div>
        </div>

        <div className="flex items-end justify-between px-4 py-3 border-t border-ink-100/60 dark:border-ink-700/60">
          <div className="flex-1 max-w-[200px]">
            <label className="block text-[10px] font-semibold text-ink-300 dark:text-ink-400 uppercase tracking-wider mb-1">Variables</label>
            <div className="space-y-1 max-h-24 overflow-y-auto">
              {variables.length === 0 && <p className="text-[10px] text-ink-300 dark:text-ink-400 italic">No variables detected</p>}
              {variables.map((v) => (
                <div key={v.name} className="flex items-center gap-2 text-[11px]">
                  <button onClick={() => toggleCompulsory(v.name)} className={`w-3 h-3 rounded-full border transition-colors ${v.compulsory ? 'bg-accent-warm border-accent-warm' : 'bg-transparent border-ink-300 dark:border-ink-500'}`} title={v.compulsory ? 'Compulsory' : 'Optional'} />
                  <span className="font-mono text-ink-600 dark:text-cream-200">{`{${v.name}}`}</span>
                  <button onClick={() => removeVariable(v.name)} className="text-ink-300 hover:text-status-error ml-auto"><X className="w-3 h-3" /></button>
                </div>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-ink-400 dark:text-ink-300 px-2 py-1 bg-ink-50 dark:bg-ink-700 rounded">{tokenCount} tokens</span>
            <button onClick={onClose} className="px-3 py-1.5 text-xs font-body font-medium text-ink-500 dark:text-ink-300 hover:bg-ink-50 dark:hover:bg-ink-700 rounded-lg transition-colors">Discard</button>
            <button onClick={handleSave} disabled={saving || !name.trim() || !content.trim()}
              className="px-4 py-1.5 text-xs font-body font-medium bg-ink-800 dark:bg-cream-200 text-cream-50 dark:text-ink-800 rounded-lg hover:bg-ink-900 dark:hover:bg-cream-300 disabled:opacity-50 transition-colors">
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>

        <div onMouseDown={handleDragStart} className="absolute bottom-0 right-0 w-5 h-5 cursor-se-resize flex items-center justify-center text-ink-300">
          <GripVertical className="w-3 h-3 rotate-45" />
        </div>
      </div>
    </div>
  )
}
