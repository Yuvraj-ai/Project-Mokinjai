import { useState } from 'react'
import { Brain, ChevronDown, ChevronRight } from 'lucide-react'

interface ThinkingCardProps {
  reasoning: string
  live?: boolean
}

/**
 * Collapsible thinking display (spec P7). Live turns show "Thinking…" until
 * the answer starts; replays show the measured label with the full text.
 */
export default function ThinkingCard({ reasoning, live }: ThinkingCardProps) {
  const [open, setOpen] = useState(false)
  if (!reasoning) return null

  return (
    <div className="mb-1.5 rounded-lg border border-line bg-surface-muted">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-[11.5px] text-ink-muted"
      >
        {open ? (
          <ChevronDown className="h-3 w-3" aria-hidden />
        ) : (
          <ChevronRight className="h-3 w-3" aria-hidden />
        )}
        <Brain className="h-3 w-3" aria-hidden />
        {live ? 'Thinking…' : 'Thought while answering'}
      </button>
      {open && (
        <p className="whitespace-pre-wrap border-t border-line px-3 py-2 text-[12px] italic text-ink-muted">
          {reasoning}
        </p>
      )}
    </div>
  )
}
