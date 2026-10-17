import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import type { OutputField } from '../../api/structuredOutputs'

interface Props {
  /** Runs the parse against the backend; resolves to the converted fields. */
  onParse: (raw: string) => Promise<{ fields: OutputField[]; title: string | null; description: string | null }>
  onUse: (parsed: { fields: OutputField[]; title: string | null; description: string | null }) => void
}

const EXAMPLE = `{
  "title": "MathReasoning",
  "description": "Reasoning steps, then the final answer.",
  "type": "object",
  "properties": {
    "answer": { "type": "string", "description": "The final answer." }
  },
  "required": ["answer"]
}`

/** Paste mode: a converter onto the same fields the builder edits. */
export default function PasteSchema({ onParse, onUse }: Props) {
  const [raw, setRaw] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [parsing, setParsing] = useState(false)

  const parse = async () => {
    setParsing(true)
    setError(null)
    try {
      onUse(await onParse(raw))
    } catch (caught: unknown) {
      const detail =
        caught && typeof caught === 'object' && 'response' in caught
          ? (caught as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null
      setError(detail || 'That schema could not be read')
    } finally {
      setParsing(false)
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] font-body text-ink-400">
        Paste a JSON Schema and it is converted into fields. References resolve against outputs you
        have already saved.
      </p>
      <textarea
        value={raw}
        onChange={(event) => setRaw(event.target.value)}
        rows={10}
        spellCheck={false}
        placeholder={EXAMPLE}
        className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 p-3 text-[11px] leading-relaxed font-mono text-ink-800 dark:text-cream-100"
      />
      {error && (
        <p className="text-xs font-body text-status-error whitespace-pre-wrap">{error}</p>
      )}
      <button
        type="button"
        onClick={() => void parse()}
        disabled={parsing || !raw.trim()}
        className="inline-flex items-center gap-2 rounded-lg bg-ink-800 dark:bg-cream-200 px-4 py-1.5 text-xs font-body font-medium text-cream-50 dark:text-ink-800 disabled:opacity-50"
      >
        {parsing && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
        Parse
      </button>
    </div>
  )
}
