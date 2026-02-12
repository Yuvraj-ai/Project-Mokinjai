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
    icon: <CheckCircle className="w-3.5 h-3.5 text-green-500" />,
    bg: 'bg-green-50',
  },
  failed: {
    icon: <XCircle className="w-3.5 h-3.5 text-red-500" />,
    bg: 'bg-red-50',
  },
  running: {
    icon: <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin" />,
    bg: 'bg-blue-50',
  },
  skipped: {
    icon: <Clock className="w-3.5 h-3.5 text-gray-400" />,
    bg: 'bg-gray-50',
  },
}

export default function ExecutionLog({ trace }: ExecutionLogProps) {
  const nodes = trace?.nodes || []

  if (nodes.length === 0) return null

  return (
    <div className="p-4">
      <h4 className="text-sm font-medium text-gray-700 mb-2">Execution Log</h4>
      <div className="space-y-1">
        {nodes.map((node, i) => {
          const config = statusConfig[node.status] || statusConfig.skipped
          return (
            <div
              key={`${node.node_id}-${i}`}
              className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs ${config.bg}`}
            >
              {config.icon}
              <span className="font-medium text-gray-700">{node.node_type}</span>
              <span className="text-gray-400 truncate flex-1">{node.node_id}</span>
              {node.duration_ms != null && (
                <span className="text-gray-400">{node.duration_ms}ms</span>
              )}
              {node.error && (
                <span className="text-red-500 truncate max-w-[100px]" title={node.error}>
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
