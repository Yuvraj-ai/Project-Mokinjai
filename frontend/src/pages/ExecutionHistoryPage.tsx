import React from 'react'
import { useEffect, useState } from 'react'
import { listExecutions } from '../api/executions'
import { listWorkspaces } from '../api/workspaces'
import { useExecutionStore } from '../store/executionStore'
import { CheckCircle, XCircle, Clock, Loader2, History, Zap } from 'lucide-react'
import type { Execution } from '../types/execution'

const statusConfig: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
  pending:   { icon: <Clock className="w-3.5 h-3.5" />,                color: '#facc15', bg: 'rgba(234,179,8,0.1)' },
  running:   { icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />, color: '#60a5fa', bg: 'rgba(59,130,246,0.1)' },
  completed: { icon: <CheckCircle className="w-3.5 h-3.5" />,          color: '#4ade80', bg: 'rgba(34,197,94,0.1)' },
  failed:    { icon: <XCircle className="w-3.5 h-3.5" />,              color: '#f87171', bg: 'rgba(239,68,68,0.1)' },
  cancelled: { icon: <XCircle className="w-3.5 h-3.5" />,              color: 'var(--text-muted)', bg: 'var(--bg-elevated)' },
}

export default function ExecutionHistoryPage() {
  const [executions, setExecutions] = useState<Execution[]>([])
  const [loading, setLoading] = useState(true)
  const { setExecution } = useExecutionStore()

  useEffect(() => {
    async function load() {
      try {
        const workspaces = await listWorkspaces()
        if (workspaces.length > 0) {
          const result = await listExecutions(workspaces[0].id)
          setExecutions(result.executions)
        }
      } catch (err) {
        console.error('Failed to load executions:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--accent-mid)' }} />
      </div>
    )
  }

  return (
    <div
      className="max-w-6xl mx-auto px-6 py-8 animate-fade-in"
      style={{ color: 'var(--text-primary)' }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.25)' }}
        >
          <History className="w-4 h-4" style={{ color: 'var(--accent-mid)' }} />
        </div>
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Execution History
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            View and inspect past workflow runs
          </p>
        </div>
      </div>

      {executions.length === 0 ? (
        <div
          className="text-center py-24 rounded-2xl"
          style={{
            background: 'var(--bg-surface)',
            border: '1px dashed var(--border-default)',
          }}
        >
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)' }}
          >
            <History className="w-7 h-7" style={{ color: 'var(--text-disabled)' }} />
          </div>
          <h3 className="text-base font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
            No executions yet
          </h3>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Run a workflow from the editor to see execution history here.
          </p>
        </div>
      ) : (
        <div
          className="rounded-2xl overflow-hidden"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
        >
          {/* Table header */}
          <div
            className="grid grid-cols-6 px-5 py-3 text-[10px] font-extrabold uppercase tracking-widest"
            style={{
              color: 'var(--text-disabled)',
              borderBottom: '1px solid var(--border-subtle)',
              background: 'var(--bg-elevated)',
            }}
          >
            {['Status', 'ID', 'Trigger', 'Duration', 'Tokens', 'Created'].map((h) => (
              <span key={h}>{h}</span>
            ))}
          </div>

          {/* Rows */}
          <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
            {executions.map((exec) => {
              const sc = statusConfig[exec.status] || statusConfig.pending
              return (
                <div
                  key={exec.id}
                  className="grid grid-cols-6 px-5 py-3.5 items-center cursor-pointer transition-colors"
                  style={{ color: 'var(--text-secondary)' }}
                  onClick={() => setExecution(exec)}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-elevated)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  {/* Status */}
                  <div className="flex items-center">
                    <span
                      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide"
                      style={{ background: sc.bg, color: sc.color }}
                    >
                      {sc.icon}
                      {exec.status}
                    </span>
                  </div>

                  {/* ID */}
                  <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                    {exec.id.slice(0, 8)}…
                  </span>

                  {/* Trigger */}
                  <span className="text-xs capitalize" style={{ color: 'var(--text-muted)' }}>
                    {exec.trigger_type || '—'}
                  </span>

                  {/* Duration */}
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {exec.execution_time_ms != null ? `${exec.execution_time_ms}ms` : '—'}
                  </span>

                  {/* Tokens */}
                  <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                    {exec.token_usage?.total_tokens ? (
                      <>
                        <Zap className="w-3 h-3" style={{ color: 'var(--node-agent)' }} />
                        {exec.token_usage.total_tokens}
                      </>
                    ) : '—'}
                  </div>

                  {/* Created */}
                  <span className="text-xs" style={{ color: 'var(--text-disabled)' }}>
                    {new Date(exec.created_at).toLocaleString()}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
