import { useState } from 'react'
import { ChevronDown, ChevronRight, Copy } from 'lucide-react'

interface Props {
  schema: Record<string, unknown> | null
}

/** Collapsed by default so it never competes with the builder for attention. */
export default function SchemaPreview({ schema }: Props) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  if (!schema) return null

  const text = JSON.stringify(schema, null, 2)

  const copy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="rounded-lg border border-line bg-surface">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-surface-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <span className="inline-flex items-center gap-2 text-[13px] font-medium text-ink">
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          Compiled JSON Schema
        </span>
        <span className="font-mono text-[11px] text-ink-muted">read-only</span>
      </button>

      {open && (
        <div className="relative border-t border-line">
          <button
            type="button"
            onClick={() => void copy()}
            className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-md border border-line bg-surface-raised px-2.5 py-1 text-xs font-medium text-ink transition-colors hover:bg-surface-muted focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Copy className="w-3 h-3" aria-hidden /> {copied ? 'copied' : 'copy'}
          </button>
          <pre className="max-h-72 overflow-auto p-3 text-xs leading-relaxed font-mono text-ink-subtle">
            {text}
          </pre>
        </div>
      )}
    </div>
  )
}
