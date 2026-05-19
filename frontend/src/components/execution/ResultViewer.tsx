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
    <div className="p-4 border-t border-gray-100">
      <div className="flex items-center justify-between mb-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-sm font-medium text-gray-700"
        >
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          Output
        </button>
        <button
          onClick={handleCopy}
          className="p-1 hover:bg-gray-100 rounded"
          title="Copy output"
        >
          {copied ? (
            <Check className="w-3.5 h-3.5 text-green-500" />
          ) : (
            <Copy className="w-3.5 h-3.5 text-gray-400" />
          )}
        </button>
      </div>
      {expanded && (
        <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-64 whitespace-pre-wrap break-words">
          {outputText}
        </pre>
      )}
    </div>
  )
}
