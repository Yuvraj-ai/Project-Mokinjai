import { useExecutionStore } from '../../store/executionStore'
import ExecutionLog from './ExecutionLog'
import ResultViewer from './ResultViewer'
import { X, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react'

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-4 h-4 text-status-warning" />,
  running: <Loader2 className="w-4 h-4 text-status-info animate-spin" />,
  completed: <CheckCircle className="w-4 h-4 text-status-success" />,
  failed: <XCircle className="w-4 h-4 text-status-error" />,
  cancelled: <XCircle className="w-4 h-4 text-ink-300" />,
}

export default function ExecutionPanel() {
  const { currentExecution, isRunning, setExecution } = useExecutionStore()

  if (!currentExecution) return null

  return (
    <div className="w-80 border-l-2 border-cream-200 bg-cream-50 flex flex-col overflow-hidden animate-slide-in-right">
      <div className="flex items-center justify-between px-4 py-3 border-b border-cream-200">
        <div className="flex items-center gap-2">
          {statusIcons[currentExecution.status] || null}
          <h3 className="font-body text-sm font-semibold text-ink-700">Execution</h3>
        </div>
        <button
          onClick={() => setExecution(null)}
          className="p-1 text-ink-300 hover:text-ink-500 hover:bg-cream-200 rounded-md transition-all duration-300"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="px-4 py-3 border-b border-cream-200 text-[11px] text-ink-300 space-y-1.5">
        <div className="flex justify-between">
          <span className="uppercase tracking-widest font-semibold">Status</span>
          <span className="font-medium text-ink-500 capitalize">{currentExecution.status}</span>
        </div>
        {currentExecution.execution_time_ms != null && (
          <div className="flex justify-between">
            <span className="uppercase tracking-widest font-semibold">Duration</span>
            <span className="font-mono text-ink-500">{currentExecution.execution_time_ms}ms</span>
          </div>
        )}
        {currentExecution.token_usage && (
          <div className="flex justify-between">
            <span className="uppercase tracking-widest font-semibold">Tokens</span>
            <span className="font-mono text-ink-500">{currentExecution.token_usage.total_tokens || 0}</span>
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
