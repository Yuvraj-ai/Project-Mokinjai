import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';

const CONDITIONAL_COLOR = '#f59e0b';

const ConditionalNode: React.FC<NodeProps> = ({ data, selected }) => {
  const conditionType = (data.conditionType as string) || 'equals';
  const conditionValue = (data.conditionValue as string) || '';

  return (
    <div className="relative">
      <BaseNode label={data.label as string || 'Conditional'} color={CONDITIONAL_COLOR} selected={selected}>
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-medium text-gray-500 uppercase">Type</span>
            <span className="text-xs font-semibold text-orange-700 bg-orange-50 px-1.5 py-0.5 rounded">
              {conditionType}
            </span>
          </div>
          {conditionValue && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-medium text-gray-500 uppercase">Value</span>
              <span className="text-xs text-gray-600 truncate max-w-[140px]">
                {conditionValue}
              </span>
            </div>
          )}
        </div>

        {/* Override the default single source handle from BaseNode */}
      </BaseNode>

      {/* True branch handle (top-right) */}
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        style={{ top: '35%' }}
        className="!w-3 !h-3 !bg-green-500 !border-2 !border-white"
      />
      <span
        className="absolute text-[9px] font-bold text-green-600 pointer-events-none"
        style={{ right: 16, top: 'calc(35% - 6px)' }}
      >
        T
      </span>

      {/* False branch handle (bottom-right) */}
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        style={{ top: '70%' }}
        className="!w-3 !h-3 !bg-red-500 !border-2 !border-white"
      />
      <span
        className="absolute text-[9px] font-bold text-red-600 pointer-events-none"
        style={{ right: 16, top: 'calc(70% - 6px)' }}
      >
        F
      </span>
    </div>
  );
};

export default ConditionalNode;
