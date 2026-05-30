import { useEffect, useState } from 'react'
import { listExecutions } from '../api/executions'
import { listWorkspaces } from '../api/workspaces'
import { useExecutionStore } from '../store/executionStore'
import { CheckCircle, XCircle, Clock, Loader2, History } from 'lucide-react'
import type { Execution } from '../types/execution'

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-3.5 h-3.5 text-status-warning" />,
  running: <Loader2 className="w-3.5 h-3.5 text-status-info animate-spin" />,
  completed: <CheckCircle className="w-3.5 h-3.5 text-status-success" />,
  failed: <XCircle className="w-3.5 h-3.5 text-status-error" />,
  cancelled: <XCircle className="w-3.5 h-3.5 text-ink-300" />,
}

const statusColors: Record<string, string> = {
  pending: 'bg-status-warning/10 text-status-warning',
  running: 'bg-status-info/10 text-status-info',
  completed: 'bg-status-success/10 text-status-success',
  failed: 'bg-status-error/10 text-status-error',
  cancelled: 'bg-ink-100 text-ink-400',
}

export default function ExecutionHistoryPage() {
  const [executions, setExecutions] = useState<Execution[]>([])
  const [loading, setLoading] = useState(true)
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const { setExecution } = useExecutionStore()

  useEffect(() => {
    async function load() {
      try {
        const workspaces = await listWorkspaces()
        if (workspaces.length > 0) {
          const wsId = workspaces[0].id
          setWorkspaceId(wsId)
          const result = await listExecutions(wsId)
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
        <Loader2 className="w-6 h-6 animate-spin text-accent" />
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="flex items-center gap-3 mb-8 animate-fade-in">
        <History className="w-6 h-6 text-ink-300" />
        <h1 className="font-display text-3xl font-normal text-ink-800 dark:text-cream-100">Execution History</h1>
      </div>

      {executions.length === 0 ? (
        <div className="text-center py-16 animate-fade-in">
          <History className="w-12 h-12 mx-auto mb-4 text-ink-200" />
          <p className="font-display text-xl text-ink-400 mb-1">No executions yet</p>
          <p className="font-body text-sm text-ink-300">Run a workflow to see execution history here</p>
        </div>
      ) : (
        <div className="bg-cream-50 rounded-xl border border-cream-200 shadow-sm overflow-hidden animate-fade-in-up">
          <table className="w-full">
            <thead>
              <tr className="bg-cream-100 border-b border-cream-200">
                <th className="text-left px-4 py-3 text-[10px] font-semibold text-ink-300 uppercase tracking-widest">Status</th>
                <th className="text-left px-4 py-3 text-[10px] font-semibold text-ink-300 uppercase tracking-widest">Execution ID</th>
                <th className="text-left px-4 py-3 text-[10px] font-semibold text-ink-300 uppercase tracking-widest">Trigger</th>
                <th className="text-left px-4 py-3 text-[10px] font-semibold text-ink-300 uppercase tracking-widest">Duration</th>
                <th className="text-left px-4 py-3 text-[10px] font-semibold text-ink-300 uppercase tracking-widest">Tokens</th>
                <th className="text-left px-4 py-3 text-[10px] font-semibold text-ink-300 uppercase tracking-widest">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cream-200">
              {executions.map((exec, i) => (
                <tr
                  key={exec.id}
                  className={`group cursor-pointer hover:bg-cream-100 transition-all duration-300 animate-fade-in stagger-${Math.min(i + 1, 8)}`}
                  onClick={() => setExecution(exec)}
                >
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium ${statusColors[exec.status] || ''}`}>
                      {statusIcons[exec.status]}
                      {exec.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-[11px] text-ink-400">
                    {exec.id.slice(0, 8)}...
                  </td>
                  <td className="px-4 py-3 font-body text-[11px] text-ink-500 capitalize">
                    {exec.trigger_type || '-'}
                  </td>
                  <td className="px-4 py-3 font-mono text-[11px] text-ink-400">
                    {exec.execution_time_ms != null ? `${exec.execution_time_ms}ms` : '-'}
                  </td>
                  <td className="px-4 py-3 font-mono text-[11px] text-ink-400">
                    {exec.token_usage?.total_tokens || '-'}
                  </td>
                  <td className="px-4 py-3 font-body text-[11px] text-ink-300">
                    {new Date(exec.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
