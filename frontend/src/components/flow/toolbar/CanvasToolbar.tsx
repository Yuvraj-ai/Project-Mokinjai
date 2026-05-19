import React, { useCallback, useState } from 'react';
import { useReactFlow } from '@xyflow/react';
import { Save, Play, ZoomIn, ZoomOut, Maximize, Loader2, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
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
  const navigate = useNavigate();
  const nodes        = useWorkflowStore((s) => s.nodes);
  const edges        = useWorkflowStore((s) => s.edges);
  const markClean    = useWorkflowStore((s) => s.markClean);
  const isDirty      = useWorkflowStore((s) => s.isDirty);
  const workflowName = useWorkflowStore((s) => s.workflowName);
  const { setExecution, setRunning, isRunning, clearNodeStatuses } = useExecutionStore();
  const [saving, setSaving] = useState(false);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await updateWorkflow(workspaceId, workflowId, { flow_definition: { nodes: nodes as any, edges: edges as any } });
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

  const iconBtn = (
    onClick: () => void,
    icon: React.ReactNode,
    title: string
  ) => (
    <button
      onClick={onClick}
      title={title}
      className="flex items-center justify-center w-7 h-7 rounded-lg transition-all"
      style={{ color: 'var(--text-muted)', background: 'transparent' }}
      onMouseEnter={e => {
        e.currentTarget.style.background = 'var(--bg-hover)';
        e.currentTarget.style.color = 'var(--text-secondary)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'transparent';
        e.currentTarget.style.color = 'var(--text-muted)';
      }}
    >
      {icon}
    </button>
  );

  return (
    <div
      className="flex items-center justify-between px-3 py-2 shrink-0"
      style={{
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-subtle)',
      }}
    >
      {/* Left — back + name + save/run */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => navigate('/workflows')}
          className="flex items-center gap-1.5 text-xs font-medium rounded-lg px-2 py-1.5 transition-all"
          style={{ color: 'var(--text-muted)' }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)'; }}
        >
          <ArrowLeft className="w-3.5 h-3.5" />
        </button>

        <div
          className="w-px h-5"
          style={{ background: 'var(--border-subtle)' }}
        />

        <span
          className="text-sm font-semibold max-w-[200px] truncate"
          style={{ color: 'var(--text-primary)' }}
        >
          {workflowName || 'Untitled Workflow'}
        </span>

        {isDirty && (
          <span
            className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide"
            style={{ background: 'rgba(234,179,8,0.15)', color: '#facc15' }}
          >
            Unsaved
          </span>
        )}

        <div
          className="w-px h-5"
          style={{ background: 'var(--border-subtle)' }}
        />

        {/* Save */}
        <button
          id="canvas-save-btn"
          onClick={handleSave}
          disabled={saving || !isDirty}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all"
          style={{
            background: isDirty ? 'rgba(99,102,241,0.15)' : 'transparent',
            color: isDirty ? 'var(--accent-mid)' : 'var(--text-disabled)',
            border: `1px solid ${isDirty ? 'rgba(99,102,241,0.3)' : 'transparent'}`,
            cursor: !isDirty ? 'not-allowed' : 'pointer',
          }}
        >
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          Save
        </button>

        {/* Run */}
        <button
          id="canvas-run-btn"
          onClick={handleRun}
          disabled={isRunning}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all"
          style={{
            background: isRunning ? 'rgba(34,197,94,0.1)' : 'rgba(34,197,94,0.15)',
            color: 'var(--status-success)',
            border: '1px solid rgba(34,197,94,0.3)',
            cursor: isRunning ? 'not-allowed' : 'pointer',
          }}
        >
          {isRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" fill="currentColor" />}
          {isRunning ? 'Running…' : 'Run'}
        </button>
      </div>

      {/* Right — zoom controls */}
      <div className="flex items-center gap-1">
        {iconBtn(() => zoomIn(),           <ZoomIn className="w-3.5 h-3.5" />,    'Zoom In')}
        {iconBtn(() => zoomOut(),          <ZoomOut className="w-3.5 h-3.5" />,   'Zoom Out')}
        {iconBtn(() => fitView({ padding: 0.2 }), <Maximize className="w-3.5 h-3.5" />, 'Fit View')}
      </div>
    </div>
  );
};

export default CanvasToolbar;
