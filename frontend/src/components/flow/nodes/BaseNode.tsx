import React from 'react';
import { Handle, Position } from '@xyflow/react';

interface BaseNodeProps {
  children: React.ReactNode;
  label: string;
  color: string;
  selected?: boolean;
}

const BaseNode: React.FC<BaseNodeProps> = ({ children, label, color, selected }) => {
  return (
    <div
      className={`bg-white rounded-lg shadow-md min-w-[200px] max-w-[280px] border border-gray-200 transition-all duration-150 ${
        selected ? 'ring-2 ring-blue-400 border-blue-400 shadow-lg' : ''
      }`}
      style={{ borderTopWidth: '3px', borderTopColor: color }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
      />

      <div className="px-3 py-2 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div
            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: color }}
          />
          <span className="text-xs font-semibold text-gray-700 truncate">{label}</span>
        </div>
      </div>

      <div className="px-3 py-2">{children}</div>

      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
      />
    </div>
  );
};

export default BaseNode;
