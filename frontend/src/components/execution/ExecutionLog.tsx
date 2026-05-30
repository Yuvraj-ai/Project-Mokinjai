import { CheckCircle, XCircle, Clock, Loader2 } from 'lucide-react'

interface NodeLog {
  node_id: string
  node_type: string
  status: string
  duration_ms?: number | null
  error?: string | null
  timestamp?: string
}

interface ExecutionLogProps {
  trace: { nodes: NodeLog[] }
}

const statusConfig: Record<string, { icon: React.ReactNode; bg: string }> = {
  completed: {
    icon: <CheckCircle className="w-3.5 h-3.5 text-status-success" />,
    bg: 'bg-status-success/10',
  },
  failed: {
    icon: <XCircle className="w-3.5 h-3.5 text-status-error" />,
    bg: 'bg-status-error/10',
  },
  running: {
    icon: <Loader2 className="w-3.5 h-3.5 text-status-info animate-spin" />,
    bg: 'bg-status-info/10',
  },
  skipped: {
    icon: <Clock className="w-3.5 h-3.5 text-ink-300" />,
    bg: 'bg-cream-100',
  },
}

export default function ExecutionLog({ trace }: ExecutionLogProps) {
  const nodes = trace?.nodes || []

  if (nodes.length === 0) return null

  return (
    <div className="p-4">
      <h4 className="font-body text-[11px] font-semibold uppercase tracking-widest text-ink-400 mb-3">Execution Log</h4>
      <div className="space-y-1.5">
        {nodes.map((node, i) => {
          const config = statusConfig[node.status] || statusConfig.skipped
          return (
            <div
              key={`${node.node_id}-${i}`}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border border-cream-200 bg-cream-100 text-xs animate-fade-in stagger-${Math.min(i + 1, 8)}`}
            >
              {config.icon}
              <span className="font-medium text-ink-500 text-[11px]">{node.node_type}</span>
              <span className="text-ink-200 font-mono text-[10px] truncate flex-1">{node.node_id}</span>
              {node.duration_ms != null && (
                <span className="text-ink-300 font-mono text-[10px]">{node.duration_ms}ms</span>
              )}
              {node.error && (
                <span className="text-status-error font-mono text-[10px] truncate max-w-[100px]" title={node.error}>
                  {node.error}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
