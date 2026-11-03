import React, { useCallback, useState, useRef, useEffect } from 'react';
import { useReactFlow } from '@xyflow/react';
import { Save, Play, ZoomIn, ZoomOut, Maximize, Loader2, Pencil } from 'lucide-react';
import useWorkflowStore from '../../../store/workflowStore';
import { useExecutionStore } from '../../../store/executionStore';
import { updateWorkflow } from '../../../api/workflows';
import { executeWorkflow } from '../../../api/executions';
import { cn } from '../../../lib/utils'

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
    'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors duration-150';

  const smallBtnClass =
    'flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md transition-colors duration-150';

  const editorNameInput =
    'text-sm font-medium text-ink bg-surface border border-line rounded-lg px-2 py-1 w-48 focus:outline-none focus:ring-2 focus:ring-ring';

  return (
    <div className="flex items-center justify-between bg-surface border-b border-line px-4 py-2.5">
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className={cn(
            btnClass,
            isDirty
              ? 'bg-primary text-primary-fg hover:bg-primary-hover shadow-sm'
              : 'border border-line bg-surface text-ink hover:bg-surface-muted',
          )}
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
          className={cn(
            btnClass,
            isRunning
              ? 'text-ink-muted bg-surface-muted cursor-not-allowed'
              : 'border border-line bg-surface text-ink hover:bg-surface-muted',
          )}
        >
          {isRunning ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          {isRunning ? 'Running...' : 'Run'}
        </button>

        <div className="w-px h-6 bg-line mx-1" />

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
            className={editorNameInput}
          />
        ) : (
          <button
            onClick={() => setEditingName(true)}
            className="flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink hover:bg-surface-muted rounded-lg px-2 py-1 transition-colors"
          >
            <span className="truncate max-w-[180px]">{workflowName}</span>
            <Pencil className="w-3 h-3 text-ink-subtle group-hover:text-ink flex-shrink-0" />
          </button>
        )}
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={() => zoomIn()}
          className={cn(smallBtnClass, 'border border-line bg-surface text-ink hover:bg-surface-muted')}
          title="Zoom In"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => zoomOut()}
          className={cn(smallBtnClass, 'border border-line bg-surface text-ink hover:bg-surface-muted')}
          title="Zoom Out"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => fitView({ padding: 0.2 })}
          className={cn(smallBtnClass, 'border border-line bg-surface text-ink hover:bg-surface-muted')}
          title="Fit View"
        >
          <Maximize className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};

export default CanvasToolbar;
