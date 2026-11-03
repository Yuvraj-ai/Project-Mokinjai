import { useExecutionStore } from '../../store/executionStore'
import ExecutionLog from './ExecutionLog'
import ResultViewer from './ResultViewer'
import { X, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react'

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-4 h-4 text-status-warning" />,
  running: <Loader2 className="w-4 h-4 text-status-info animate-spin" />,
  completed: <CheckCircle className="w-4 h-4 text-status-success" />,
  failed: <XCircle className="w-4 h-4 text-status-error" />,
  cancelled: <XCircle className="w-4 h-4 text-ink-muted" />,
}

export default function ExecutionPanel() {
  const { currentExecution, isRunning, setExecution } = useExecutionStore()

  if (!currentExecution) return null

  return (
    <div className="w-80 border-l-2 border-line bg-surface-muted flex flex-col overflow-hidden animate-slide-in-right">
      <div className="flex items-center justify-between px-4 py-3 border-b border-line">
        <div className="flex items-center gap-2">
          {statusIcons[currentExecution.status] || null}
          <h3 className="font-body text-sm font-semibold text-ink">Execution</h3>
        </div>
        <button
          onClick={() => setExecution(null)}
          className="p-1 text-ink-muted hover:text-ink hover:bg-surface-muted rounded-md transition-all duration-300"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="px-4 py-3 border-b border-line text-[11px] text-ink-muted space-y-1.5">
        <div className="flex justify-between">
          <span className="uppercase tracking-widest font-semibold">Status</span>
          <span className="font-medium text-ink-muted capitalize">{currentExecution.status}</span>
        </div>
        {currentExecution.execution_time_ms != null && (
          <div className="flex justify-between">
            <span className="uppercase tracking-widest font-semibold">Duration</span>
            <span className="font-mono text-ink-muted">{currentExecution.execution_time_ms}ms</span>
          </div>
        )}
        {currentExecution.token_usage && (
          <div className="flex justify-between">
            <span className="uppercase tracking-widest font-semibold">Tokens</span>
            <span className="font-mono text-ink-muted">{currentExecution.token_usage.total_tokens || 0}</span>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-auto">
        {currentExecution.execution_trace && (
          <ExecutionLog trace={currentExecution.execution_trace} />
        )}

        {currentExecution.output_data && (
          <ResultViewer data={currentExecution.output_data} />
        )}

        {currentExecution.error_message && (
          <div className="p-4">
            <h4 className="font-body text-[11px] font-semibold uppercase tracking-widest text-status-error mb-2">Error</h4>
            <p className="font-mono text-[11px] text-status-error bg-status-error/10 p-3 rounded-lg">
              {currentExecution.error_message}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
