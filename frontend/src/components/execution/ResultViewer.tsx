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
    <div className="p-4 border-t border-cream-200">
      <div className="flex items-center justify-between mb-3">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 font-body text-[11px] font-semibold uppercase tracking-widest text-ink-500 hover:text-ink-700 transition-colors duration-300"
        >
          {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          Output
        </button>
        <button
          onClick={handleCopy}
          className="p-1 text-ink-200 hover:text-ink-500 hover:bg-cream-200 rounded-md transition-all duration-300"
          title="Copy output"
        >
          {copied ? (
            <Check className="w-3.5 h-3.5 text-accent-warm" />
          ) : (
            <Copy className="w-3.5 h-3.5" />
          )}
        </button>
      </div>
      <div className={`overflow-hidden transition-all duration-500 ${expanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'}`}>
        <pre className="font-mono text-[11px] text-ink-500 bg-cream-100 border border-cream-200 p-3 rounded-lg overflow-auto max-h-64 whitespace-pre-wrap break-words">
          {outputText}
        </pre>
      </div>
    </div>
  )
}
