import React, { useCallback, useState } from 'react';
import { useReactFlow } from '@xyflow/react';
import { Save, Play, ZoomIn, ZoomOut, Maximize, Loader2 } from 'lucide-react';
import useWorkflowStore from '../../../store/workflowStore';
import { useExecutionStore } from '../../../store/executionStore';
import { updateWorkflow } from '../../../api/workflows';
import { executeWorkflow } from '../../../api/executions';

interface CanvasToolbarProps {
  workspaceId: string;
  workflowId: string;
}

const CanvasToolbar: React.FC<CanvasToolbarProps> = ({ workspaceId, workflowId }) => {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const markClean = useWorkflowStore((s) => s.markClean);
  const isDirty = useWorkflowStore((s) => s.isDirty);
  const { setExecution, setRunning, isRunning, clearNodeStatuses } = useExecutionStore();
  const [saving, setSaving] = useState(false);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await updateWorkflow(workspaceId, workflowId, {
        flow_definition: { nodes, edges },
      });
      markClean();
    } catch (error) {
      console.error('Save error:', error);
    } finally {
      setSaving(false);
    }
  }, [workspaceId, workflowId, nodes, edges, markClean]);

  const handleRun = useCallback(async () => {
    clearNodeStatuses();
    setRunning(true);
    try {
      const execution = await executeWorkflow(workspaceId, workflowId);
      setExecution(execution);
    } catch (error) {
      console.error('Execution error:', error);
      setRunning(false);
    }
  }, [workspaceId, workflowId, clearNodeStatuses, setRunning, setExecution]);

  const btnClass =
    'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors';

  return (
    <div className="flex items-center justify-between bg-white border-b border-gray-200 px-4 py-2">
      <div className="flex items-center gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className={`${btnClass} ${
            isDirty
              ? 'bg-blue-500 text-white hover:bg-blue-600'
              : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
          }`}
        >
          {saving ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Save className="w-3.5 h-3.5" />
          )}
          Save
        </button>
        <button
          onClick={handleRun}
          disabled={isRunning}
          className={`${btnClass} ${
            isRunning
              ? 'bg-green-400 text-white cursor-not-allowed'
              : 'bg-green-500 text-white hover:bg-green-600'
          }`}
        >
          {isRunning ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5" />
          )}
          {isRunning ? 'Running...' : 'Run'}
        </button>
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={() => zoomIn()}
          className={`${btnClass} bg-gray-100 text-gray-600 hover:bg-gray-200`}
          title="Zoom In"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => zoomOut()}
          className={`${btnClass} bg-gray-100 text-gray-600 hover:bg-gray-200`}
          title="Zoom Out"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => fitView({ padding: 0.2 })}
          className={`${btnClass} bg-gray-100 text-gray-600 hover:bg-gray-200`}
          title="Fit View"
        >
          <Maximize className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};

export default CanvasToolbar;
