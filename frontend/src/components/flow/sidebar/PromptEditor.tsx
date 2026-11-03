import { useState, useEffect, useCallback, useRef } from 'react'
import { X, GripVertical } from 'lucide-react'
import { createPrompt, updatePrompt, type PromptTemplate } from '../../../api/prompts'
import Button from '../../ui/Button'

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

  const labelClass = 'mb-1.5 block text-[13px] font-medium text-ink'
  const controlClass =
    'w-full rounded-lg border border-line bg-surface px-3 py-2 text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring transition-colors'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40 dark:bg-black/60" onClick={onClose} />
      <div
        className="relative bg-surface rounded-2xl shadow-drawer border border-line flex flex-col overflow-hidden animate-scale-in"
        style={{ width: size.width, height: size.height }}
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-line">
          <h2 className="text-[15px] font-semibold text-ink">{prompt ? 'Edit Prompt' : 'New Prompt'}</h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-md hover:bg-surface-muted text-ink-subtle hover:text-ink transition-colors"><X className="w-4 h-4" /></button>
        </div>

        <div className="flex-1 overflow-auto p-5 space-y-4">
          <div>
            <label className={labelClass}>Name</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Prompt name"
              className={controlClass + ' text-sm'} />
          </div>
          <div>
            <label className={labelClass}>Description</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Brief description..." rows={2}
              className={controlClass + ' text-sm resize-none'} />
          </div>
          <div className="flex-1">
            <label className={labelClass}>System Prompt</label>
            <textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="Write your system prompt here. Use {variable_name} for variables..."
              className={controlClass + ' text-[13px] font-mono resize-none'}
              style={{ minHeight: 200 }} />
          </div>
        </div>

        <div className="flex items-end justify-between px-5 py-3.5 border-t border-line">
          <div className="flex-1 max-w-[220px]">
            <label className="mb-1.5 block text-[13px] font-medium text-ink">Variables</label>
            <div className="space-y-1 max-h-24 overflow-y-auto">
              {variables.length === 0 && <p className="text-xs text-ink-subtle italic">No variables detected</p>}
              {variables.map((v) => (
                <div key={v.name} className="flex items-center gap-2 text-xs">
                  <button onClick={() => toggleCompulsory(v.name)} aria-label={v.compulsory ? 'Compulsory' : 'Optional'} className={`w-3 h-3 rounded-full border transition-colors ${v.compulsory ? 'bg-primary border-primary' : 'bg-transparent border-line-strong'}`} title={v.compulsory ? 'Compulsory' : 'Optional'} />
                  <span className="font-mono text-ink">{`{${v.name}}`}</span>
                  <button onClick={() => removeVariable(v.name)} aria-label="Remove variable" className="text-ink-subtle hover:text-status-error ml-auto"><X className="w-3 h-3" /></button>
                </div>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="text-xs font-mono text-ink-muted px-2 py-1 bg-surface-muted border border-line rounded-md"
              title="Live estimate while typing. The saved prompt shows the exact tiktoken count."
            >
              ~{tokenCount} tokens
            </span>
            <Button variant="ghost" size="sm" onClick={onClose}>Discard</Button>
            <Button size="sm" loading={saving} disabled={!name.trim() || !content.trim()} onClick={handleSave}>
              Save
            </Button>
          </div>
        </div>

        <div onMouseDown={handleDragStart} className="absolute bottom-0 right-0 w-5 h-5 cursor-se-resize flex items-center justify-center text-ink-subtle">
          <GripVertical className="w-3 h-3 rotate-45" />
        </div>
      </div>
    </div>
  )
}
