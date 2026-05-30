import React, { useCallback, useState, useRef, useEffect } from 'react';
import { useReactFlow } from '@xyflow/react';
import { Save, Play, ZoomIn, ZoomOut, Maximize, Loader2, Pencil } from 'lucide-react';
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
  const workflowName = useWorkflowStore((s) => s.workflowName);
  const setWorkflowName = useWorkflowStore((s) => s.setWorkflowName);
  const { setExecution, setRunning, isRunning, clearNodeStatuses } = useExecutionStore();
  const [saving, setSaving] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState(workflowName);
  const nameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setNameValue(workflowName);
  }, [workflowName]);

  useEffect(() => {
    if (editingName && nameInputRef.current) {
      nameInputRef.current.focus();
      nameInputRef.current.select();
    }
  }, [editingName]);

  const handleNameSubmit = () => {
    const trimmed = nameValue.trim();
    if (trimmed && trimmed !== workflowName) {
      setWorkflowName(trimmed);
    } else {
      setNameValue(workflowName);
    }
    setEditingName(false);
  };

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await updateWorkflow(workspaceId, workflowId, {
        name: workflowName,
        flow_definition: {
          nodes: nodes.map((n) => ({ id: n.id, type: n.type || 'unknown', position: n.position, data: n.data })),
          edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle || undefined, targetHandle: e.targetHandle || undefined })),
        },
      });
      markClean();
    } catch (error) {
      console.error('Save error:', error);
    } finally {
      setSaving(false);
    }
  }, [workspaceId, workflowId, nodes, edges, markClean, workflowName]);

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
    'flex items-center gap-2 px-4 py-2 text-sm font-body font-medium rounded-lg transition-all duration-200';

  const smallBtnClass =
    'flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-body font-medium rounded-md transition-all duration-200';

  return (
    <div className="flex items-center justify-between bg-white dark:bg-ink-800 border-b border-ink-100/60 dark:border-ink-700/60 px-4 py-2.5">
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className={`${btnClass} ${
            isDirty
              ? 'bg-ink-800 dark:bg-cream-200 text-cream-50 dark:text-ink-800 hover:bg-ink-900 dark:hover:bg-cream-300 shadow-sm'
              : 'bg-ink-50 dark:bg-ink-700 text-ink-400 dark:text-ink-300 hover:bg-ink-100 dark:hover:bg-ink-600 hover:text-ink-500'
          }`}
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Save
        </button>
        <button
          onClick={handleRun}
          disabled={isRunning}
          className={`${btnClass} ${
            isRunning
              ? 'bg-status-success/60 text-cream-50 cursor-not-allowed'
              : 'bg-status-success text-cream-50 hover:bg-status-success/90 shadow-sm'
          }`}
        >
          {isRunning ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          {isRunning ? 'Running...' : 'Run'}
        </button>

        <div className="w-px h-6 bg-ink-100/60 dark:bg-ink-700/60 mx-1" />

        {editingName ? (
          <input
            ref={nameInputRef}
            type="text"
            value={nameValue}
            onChange={(e) => setNameValue(e.target.value)}
            onBlur={handleNameSubmit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleNameSubmit();
              if (e.key === 'Escape') { setNameValue(workflowName); setEditingName(false); }
            }}
            className="font-body text-sm font-medium text-ink-800 dark:text-cream-100 bg-ink-50 dark:bg-ink-700 border border-ink-200 dark:border-ink-600 rounded px-2 py-1 w-48 focus:outline-none focus:ring-1 focus:ring-accent-warm/40 focus:border-accent-warm"
          />
        ) : (
          <button
            onClick={() => setEditingName(true)}
            className="flex items-center gap-1.5 text-sm font-body font-medium text-ink-700 dark:text-cream-200 hover:text-ink-900 dark:hover:text-cream-100 hover:bg-ink-50 dark:hover:bg-ink-700 rounded px-2 py-1 transition-colors group"
          >
            <span className="truncate max-w-[180px]">{workflowName}</span>
            <Pencil className="w-3 h-3 text-ink-300 dark:text-ink-400 group-hover:text-ink-500 flex-shrink-0" />
          </button>
        )}
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={() => zoomIn()}
          className={`${smallBtnClass} bg-ink-50 dark:bg-ink-700 text-ink-400 dark:text-ink-300 hover:bg-ink-100 dark:hover:bg-ink-600 hover:text-ink-500`}
          title="Zoom In"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => zoomOut()}
          className={`${smallBtnClass} bg-ink-50 dark:bg-ink-700 text-ink-400 dark:text-ink-300 hover:bg-ink-100 dark:hover:bg-ink-600 hover:text-ink-500`}
          title="Zoom Out"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => fitView({ padding: 0.2 })}
          className={`${smallBtnClass} bg-ink-50 dark:bg-ink-700 text-ink-400 dark:text-ink-300 hover:bg-ink-100 dark:hover:bg-ink-600 hover:text-ink-500`}
          title="Fit View"
        >
          <Maximize className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};

export default CanvasToolbar;
