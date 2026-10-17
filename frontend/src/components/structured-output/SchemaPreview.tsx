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
    <div className="rounded-lg border border-ink-100 dark:border-ink-700 bg-white dark:bg-ink-800">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between px-3 py-2 text-left"
      >
        <span className="inline-flex items-center gap-1.5 text-[11px] font-body text-ink-500 dark:text-ink-200">
          {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          Compiled JSON Schema
        </span>
        <span className="text-[10px] text-ink-400">read-only</span>
      </button>

      {open && (
        <div className="relative border-t border-cream-200 dark:border-ink-700">
          <button
            type="button"
            onClick={() => void copy()}
            className="absolute right-2 top-2 inline-flex items-center gap-1 rounded border border-ink-100 dark:border-ink-600 bg-white/90 dark:bg-ink-800/90 px-1.5 py-0.5 text-[10px] font-body text-ink-500 dark:text-ink-200"
          >
            <Copy className="w-3 h-3" /> {copied ? 'copied' : 'copy'}
          </button>
          <pre className="max-h-72 overflow-auto p-3 text-[11px] leading-relaxed font-mono text-ink-500 dark:text-ink-200">
            {text}
          </pre>
        </div>
      )}
    </div>
  )
}
