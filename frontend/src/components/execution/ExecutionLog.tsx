import React from 'react';
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

const statusConfig: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
  completed: {
    icon: <CheckCircle className="w-3 h-3" />,
    color: 'var(--status-success)',
    bg: 'rgba(34,197,94,0.08)',
  },
  failed: {
    icon: <XCircle className="w-3 h-3" />,
    color: 'var(--status-error)',
    bg: 'rgba(239,68,68,0.08)',
  },
  running: {
    icon: <Loader2 className="w-3 h-3 animate-spin" />,
    color: 'var(--status-info)',
    bg: 'rgba(59,130,246,0.08)',
  },
  skipped: {
    icon: <Clock className="w-3 h-3" />,
    color: 'var(--text-disabled)',
    bg: 'transparent',
  },
}

export default function ExecutionLog({ trace }: ExecutionLogProps) {
  const nodes = trace?.nodes || []
  if (nodes.length === 0) return null

  return (
    <div className="p-4">
      <h4
        className="text-[9px] font-extrabold uppercase tracking-widest mb-3"
        style={{ color: 'var(--text-disabled)' }}
      >
        Execution Trace
      </h4>
      <div className="space-y-1">
        {nodes.map((node, i) => {
          const config = statusConfig[node.status] || statusConfig.skipped
          return (
            <div
              key={`${node.node_id}-${i}`}
              className="flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs"
              style={{
                background: config.bg,
                border: `1px solid ${config.color}20`,
              }}
            >
              <span style={{ color: config.color, flexShrink: 0 }}>{config.icon}</span>
              <span className="font-semibold capitalize flex-shrink-0" style={{ color: 'var(--text-secondary)' }}>
                {node.node_type}
              </span>
              <span className="truncate flex-1 font-mono text-[9px]" style={{ color: 'var(--text-disabled)' }}>
                {node.node_id}
              </span>
              {node.duration_ms != null && (
                <span className="flex-shrink-0 text-[9px]" style={{ color: 'var(--text-muted)' }}>
                  {node.duration_ms}ms
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
