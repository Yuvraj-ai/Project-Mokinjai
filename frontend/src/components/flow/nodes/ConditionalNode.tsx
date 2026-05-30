import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';

const CONDITIONAL_COLOR = '#BC6C25';

const ConditionalNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const conditionType = (data.conditionType as string) || 'equals';
  const conditionValue = (data.conditionValue as string) || '';

  return (
    <div className="relative">
      <BaseNode id={id} label={data.label as string || 'Conditional'} color={CONDITIONAL_COLOR} selected={selected}>
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5">
            <span className="font-body text-[9px] font-semibold text-ink-300 dark:text-ink-400 uppercase tracking-widest">Type</span>
            <span
              className="font-body text-[11px] font-semibold px-1.5 py-0.5 rounded"
              style={{ backgroundColor: `${CONDITIONAL_COLOR}15`, color: CONDITIONAL_COLOR }}
            >
              {conditionType}
            </span>
          </div>
          {conditionValue && (
            <div className="flex items-center gap-1.5">
              <span className="font-body text-[9px] font-semibold text-ink-300 dark:text-ink-400 uppercase tracking-widest">Value</span>
              <span className="font-body text-[11px] text-ink-500 dark:text-cream-200 truncate max-w-[140px]">
                {conditionValue}
              </span>
            </div>
          )}
        </div>
      </BaseNode>

      {/* True branch handle (top-right) */}
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        style={{ top: '35%' }}
        className="!w-2.5 !h-2.5 !bg-[#2D6A4F] !border-2 !border-white"
      />
      <span
        className="absolute font-body text-[9px] font-bold text-[#2D6A4F] pointer-events-none"
        style={{ right: 14, top: 'calc(35% - 5px)' }}
      >
        T
      </span>

      {/* False branch handle (bottom-right) */}
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        style={{ top: '70%' }}
        className="!w-2.5 !h-2.5 !bg-[#9B2226] !border-2 !border-white"
      />
      <span
        className="absolute font-body text-[9px] font-bold text-[#9B2226] pointer-events-none"
        style={{ right: 14, top: 'calc(70% - 5px)' }}
      >
        F
      </span>
    </div>
  );
};

export default ConditionalNode;
