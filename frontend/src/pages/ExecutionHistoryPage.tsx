import { useEffect, useState } from 'react'
import { listExecutions } from '../api/executions'
import { listWorkspaces } from '../api/workspaces'
import { useExecutionStore } from '../store/executionStore'
import { CheckCircle, XCircle, Clock, Loader2, History } from 'lucide-react'
import type { Execution } from '../types/execution'
import { EmptyState, Spinner } from '../components/ui/Feedback'
import Badge from '../components/ui/Badge'
import { TableFrame, Table, Th, Td, Tr } from '../components/ui/Table'

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-3.5 h-3.5" aria-hidden />,
  running: <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />,
  completed: <CheckCircle className="w-3.5 h-3.5" aria-hidden />,
  failed: <XCircle className="w-3.5 h-3.5" aria-hidden />,
  cancelled: <XCircle className="w-3.5 h-3.5" aria-hidden />,
}

const statusTones: Record<string, 'neutral' | 'success' | 'warning' | 'danger' | 'info'> = {
  pending: 'warning',
  running: 'info',
  completed: 'success',
  failed: 'danger',
  cancelled: 'neutral',
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
        <Spinner className="w-6 h-6" />
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="mb-8 animate-fade-in">
        <h1 className="text-2xl font-semibold text-ink tracking-tight">Execution History</h1>
        <p className="mt-1 text-sm text-ink-muted">Every workflow run, newest first. Agent chats live in the Playground.</p>
      </div>

      {executions.length === 0 ? (
        <div className="bg-surface border border-line rounded-xl animate-fade-in">
          <EmptyState
            icon={History}
            title="No executions yet"
            description="Run a workflow to see execution history here"
          />
        </div>
      ) : (
        <TableFrame className="animate-fade-in-up">
          <Table>
            <thead>
              <tr>
                <Th>Status</Th>
                <Th>Execution ID</Th>
                <Th>Trigger</Th>
                <Th numeric>Duration</Th>
                <Th numeric>Tokens</Th>
                <Th>Created</Th>
              </tr>
            </thead>
            <tbody>
              {executions.map((exec, i) => (
                <Tr
                  key={exec.id}
                  onClick={() => setExecution(exec)}
                  className={`animate-fade-in stagger-${Math.min(i + 1, 8)}`}
                >
                  <Td>
                    <span className="inline-flex items-center gap-1.5">
                      {statusIcons[exec.status]}
                      <Badge tone={statusTones[exec.status] ?? 'neutral'} dot>
                        {exec.status}
                      </Badge>
                    </span>
                  </Td>
                  <Td mono className="text-ink-muted">
                    {exec.id.slice(0, 8)}…
                  </Td>
                  <Td className="capitalize">{exec.trigger_type || '-'}</Td>
                  <Td numeric className="text-ink-muted">
                    {exec.execution_time_ms != null ? `${exec.execution_time_ms}ms` : '-'}
                  </Td>
                  <Td numeric className="text-ink-muted">
                    {exec.token_usage?.total_tokens || '-'}
                  </Td>
                  <Td className="text-ink-muted">
                    {new Date(exec.created_at).toLocaleString()}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </TableFrame>
      )}
    </div>
  )
}
