import { useExecutionStore } from '../../store/executionStore'
import ExecutionLog from './ExecutionLog'
import ResultViewer from './ResultViewer'
import { X, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react'

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-4 h-4 text-yellow-500" />,
  running: <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle className="w-4 h-4 text-green-500" />,
  failed: <XCircle className="w-4 h-4 text-red-500" />,
  cancelled: <XCircle className="w-4 h-4 text-gray-500" />,
}

export default function ExecutionPanel() {
  const { currentExecution, isRunning, setExecution } = useExecutionStore()

  if (!currentExecution) return null

  return (
    <div className="w-80 border-l border-gray-200 bg-white flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="flex items-center gap-2">
          {statusIcons[currentExecution.status] || null}
          <h3 className="font-semibold text-sm">Execution</h3>
        </div>
        <button
          onClick={() => setExecution(null)}
          className="p-1 hover:bg-gray-100 rounded"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="px-4 py-2 border-b border-gray-100 text-xs text-gray-500 space-y-1">
        <div className="flex justify-between">
          <span>Status</span>
          <span className="font-medium capitalize">{currentExecution.status}</span>
        </div>
        {currentExecution.execution_time_ms != null && (
          <div className="flex justify-between">
            <span>Duration</span>
            <span className="font-medium">{currentExecution.execution_time_ms}ms</span>
          </div>
        )}
        {currentExecution.token_usage && (
          <div className="flex justify-between">
            <span>Tokens</span>
            <span className="font-medium">{currentExecution.token_usage.total_tokens || 0}</span>
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
            <h4 className="text-sm font-medium text-red-600 mb-1">Error</h4>
            <p className="text-xs text-red-500 bg-red-50 p-2 rounded">
              {currentExecution.error_message}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
