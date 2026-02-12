import { useEffect, useState } from 'react'
import { listExecutions } from '../api/executions'
import { listWorkspaces } from '../api/workspaces'
import { useExecutionStore } from '../store/executionStore'
import { CheckCircle, XCircle, Clock, Loader2, History } from 'lucide-react'
import type { Execution } from '../types/execution'

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-4 h-4 text-yellow-500" />,
  running: <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle className="w-4 h-4 text-green-500" />,
  failed: <XCircle className="w-4 h-4 text-red-500" />,
  cancelled: <XCircle className="w-4 h-4 text-gray-400" />,
}

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
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
        <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <History className="w-6 h-6 text-gray-600" />
        <h1 className="text-2xl font-bold text-gray-900">Execution History</h1>
      </div>

      {executions.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <History className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p>No executions yet</p>
          <p className="text-sm mt-1">Run a workflow to see execution history here</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Execution ID</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Trigger</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Duration</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Tokens</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {executions.map((exec) => (
                <tr
                  key={exec.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setExecution(exec)}
                >
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[exec.status] || ''}`}>
                      {statusIcons[exec.status]}
                      {exec.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 font-mono">
                    {exec.id.slice(0, 8)}...
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 capitalize">
                    {exec.trigger_type || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {exec.execution_time_ms != null ? `${exec.execution_time_ms}ms` : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {exec.token_usage?.total_tokens || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
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
