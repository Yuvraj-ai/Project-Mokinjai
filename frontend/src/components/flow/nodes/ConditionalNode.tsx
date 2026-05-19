import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { GitBranch } from 'lucide-react';
import BaseNode from './BaseNode';

const COLOR = 'var(--node-conditional)';

const ConditionalNode: React.FC<NodeProps> = ({ data, selected }) => {
  const conditionType  = (data.conditionType as string) || 'equals';
  const conditionValue = (data.conditionValue as string) || '';

  return (
    <div className="relative">
      <BaseNode
        label={(data.label as string) || 'Conditional'}
        accentColor={COLOR}
        icon={<GitBranch className="w-3 h-3" />}
        selected={selected}
      >
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5">
            <p className="node-field-label">Type</p>
            <span
              className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wide"
              style={{ background: 'rgba(234,179,8,0.15)', color: 'var(--node-conditional)' }}
            >
              {conditionType}
            </span>
          </div>
          {conditionValue && (
            <div className="flex items-center gap-1.5">
              <p className="node-field-label">Value</p>
              <span className="text-[10px] truncate max-w-[130px]" style={{ color: 'var(--text-secondary)' }}>
                {conditionValue}
              </span>
            </div>
          )}
        </div>
      </BaseNode>

      {/* True branch handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        style={{
          top: '38%',
          background: 'var(--status-success)',
          border: '2px solid var(--bg-elevated)',
          width: 10,
          height: 10,
          borderRadius: '50%',
        }}
      />
      <span
        className="absolute text-[8px] font-bold pointer-events-none"
        style={{ right: 14, top: 'calc(38% - 7px)', color: 'var(--status-success)' }}
      >
        T
      </span>

      {/* False branch handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        style={{
          top: '68%',
          background: 'var(--status-error)',
          border: '2px solid var(--bg-elevated)',
          width: 10,
          height: 10,
          borderRadius: '50%',
        }}
      />
      <span
        className="absolute text-[8px] font-bold pointer-events-none"
        style={{ right: 14, top: 'calc(68% - 7px)', color: 'var(--status-error)' }}
      >
        F
      </span>
    </div>
  );
};

export default ConditionalNode;
