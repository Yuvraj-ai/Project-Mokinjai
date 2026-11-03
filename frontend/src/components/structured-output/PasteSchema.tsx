import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import type { OutputField } from '../../api/structuredOutputs'
import Button from '../ui/Button'

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
    <div className="space-y-3">
      <p className="text-xs text-ink-muted leading-relaxed">
        Paste a JSON Schema and it is converted into fields. References resolve against outputs you
        have already saved.
      </p>
      <textarea
        value={raw}
        onChange={(event) => setRaw(event.target.value)}
        rows={10}
        spellCheck={false}
        placeholder={EXAMPLE}
        className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-xs leading-relaxed font-mono text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
      />
      {error && (
        <p className="text-xs text-status-error whitespace-pre-wrap">{error}</p>
      )}
      <Button disabled={parsing || !raw.trim()} onClick={() => void parse()} className="w-full sm:w-auto">
        {parsing && <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />}
        Parse
      </Button>
    </div>
  )
}
