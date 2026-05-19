import React from 'react';
import { useExecutionStore } from '../../store/executionStore'
import ExecutionLog from './ExecutionLog'
import ResultViewer from './ResultViewer'
import { X, Clock, CheckCircle, XCircle, Loader2, Zap } from 'lucide-react'

const statusConfig: Record<string, { icon: React.ReactNode; color: string; bg: string; label: string }> = {
  pending:   { icon: <Clock className="w-3.5 h-3.5" />,                      color: '#facc15', bg: 'rgba(234,179,8,0.1)',   label: 'Pending' },
  running:   { icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,       color: '#60a5fa', bg: 'rgba(59,130,246,0.1)',  label: 'Running' },
  completed: { icon: <CheckCircle className="w-3.5 h-3.5" />,                color: '#4ade80', bg: 'rgba(34,197,94,0.1)',   label: 'Completed' },
  failed:    { icon: <XCircle className="w-3.5 h-3.5" />,                    color: '#f87171', bg: 'rgba(239,68,68,0.1)',   label: 'Failed' },
  cancelled: { icon: <XCircle className="w-3.5 h-3.5" />,                    color: 'var(--text-muted)', bg: 'var(--bg-elevated)', label: 'Cancelled' },
}

export default function ExecutionPanel() {
  const { currentExecution, setExecution } = useExecutionStore()
  if (!currentExecution) return null

  const sc = statusConfig[currentExecution.status] || statusConfig.pending

  return (
    <div
      className="w-80 flex flex-col overflow-hidden animate-slide-in"
      style={{
        background: 'var(--bg-surface)',
        borderLeft: '1px solid var(--border-subtle)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 shrink-0"
        style={{ borderBottom: '1px solid var(--border-subtle)' }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: sc.bg, color: sc.color }}
          >
            {sc.icon}
          </div>
          <div>
            <p className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>Execution</p>
            <p className="text-[10px]" style={{ color: sc.color }}>{sc.label}</p>
          </div>
        </div>
        <button
          onClick={() => setExecution(null)}
          className="w-6 h-6 rounded flex items-center justify-center transition-colors"
          style={{ color: 'var(--text-muted)' }}
          onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Stats */}
      <div
        className="px-4 py-3 grid grid-cols-2 gap-3 shrink-0"
        style={{ borderBottom: '1px solid var(--border-subtle)' }}
      >
        {[
          {
            label: 'Duration',
            value: currentExecution.execution_time_ms != null
              ? `${currentExecution.execution_time_ms}ms`
              : '—',
            icon: <Clock className="w-3 h-3" />,
            color: 'var(--text-muted)',
          },
          {
            label: 'Tokens',
            value: currentExecution.token_usage?.total_tokens ?? '—',
            icon: <Zap className="w-3 h-3" />,
            color: 'var(--node-agent)',
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-lg p-2.5"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}
          >
            <div className="flex items-center gap-1.5 mb-1" style={{ color: stat.color }}>
              {stat.icon}
              <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-disabled)' }}>{stat.label}</span>
            </div>
            <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-auto">
        {currentExecution.execution_trace && (
          <ExecutionLog trace={currentExecution.execution_trace} />
        )}
        {currentExecution.output_data && (
          <ResultViewer data={currentExecution.output_data} />
        )}
        {currentExecution.error_message && (
          <div className="p-4">
            <h4 className="text-xs font-bold mb-2 uppercase tracking-wider" style={{ color: '#f87171' }}>Error</h4>
            <pre
              className="text-[10px] rounded-lg p-3 overflow-auto leading-relaxed"
              style={{
                background: 'rgba(239,68,68,0.08)',
                border: '1px solid rgba(239,68,68,0.2)',
                color: '#fca5a5',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {currentExecution.error_message}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
