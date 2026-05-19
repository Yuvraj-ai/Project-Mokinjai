import { useState } from 'react'
import { ChevronDown, ChevronRight, Copy, Check } from 'lucide-react'

interface ResultViewerProps {
  data: Record<string, any>
}

export default function ResultViewer({ data }: ResultViewerProps) {
  const [expanded, setExpanded] = useState(true)
  const [copied, setCopied] = useState(false)

  const outputText = typeof data === 'string'
    ? data
    : data?.output
      ? String(data.output)
      : JSON.stringify(data, null, 2)

  const handleCopy = () => {
    navigator.clipboard.writeText(outputText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className="p-4"
      style={{ borderTop: '1px solid var(--border-subtle)' }}
    >
      <div className="flex items-center justify-between mb-3">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest transition-colors"
          style={{ color: 'var(--text-muted)' }}
        >
          {expanded
            ? <ChevronDown className="w-3.5 h-3.5" />
            : <ChevronRight className="w-3.5 h-3.5" />}
          Output
        </button>
        <button
          onClick={handleCopy}
          title="Copy output"
          className="w-6 h-6 rounded flex items-center justify-center transition-all"
          style={{ color: copied ? 'var(--status-success)' : 'var(--text-muted)' }}
          onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
        >
          {copied
            ? <Check className="w-3.5 h-3.5" />
            : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>
      {expanded && (
        <pre
          className="text-[10px] leading-relaxed overflow-auto max-h-64 rounded-lg p-3 font-mono whitespace-pre-wrap break-words"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-secondary)',
          }}
        >
          {outputText}
        </pre>
      )}
    </div>
  )
}
