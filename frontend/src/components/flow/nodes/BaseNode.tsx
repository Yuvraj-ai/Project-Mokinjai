import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { X } from 'lucide-react';
import useWorkflowStore from '../../../store/workflowStore';

interface BaseNodeProps {
  children: React.ReactNode;
  label: string;
  color: string;
  selected?: boolean;
  id?: string;
}

const BaseNode: React.FC<BaseNodeProps> = ({ children, label, color, selected, id }) => {
  const removeNode = useWorkflowStore((s) => s.removeNode);

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (id) removeNode(id);
  };

  return (
    <div
      className={`bg-white dark:bg-ink-800 rounded-lg border border-ink-100/80 dark:border-ink-700/60 transition-all duration-150 ${
        selected ? 'ring-2 ring-accent-warm/60 shadow-md' : 'shadow-sm'
      }`}
      style={{ borderLeftWidth: '3px', borderLeftColor: color, width: 180 }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-ink-200 !border-2 !border-white !-left-1.5"
      />

      <div className="px-2.5 py-1.5 border-b border-ink-100/60 flex items-center justify-between">
        <div className="flex items-center gap-1.5 min-w-0">
          <div
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: color }}
          />
          <span className="font-body text-[11px] font-semibold text-ink-700 dark:text-cream-200 truncate leading-tight">{label}</span>
        </div>
        {selected && (
          <button
            onClick={handleDelete}
            className="flex-shrink-0 p-0.5 rounded hover:bg-status-error/10 text-ink-300 hover:text-status-error transition-colors"
            title="Delete node"
          >
            <X className="w-3 h-3" />
          </button>
        )}
      </div>

      <div className="px-2.5 py-2">{children}</div>

      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-ink-200 !border-2 !border-white !-right-1.5"
      />
    </div>
  );
};

export default BaseNode;
