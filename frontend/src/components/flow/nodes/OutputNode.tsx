import React from 'react';
import { NodeProps } from '@xyflow/react';
import { FileText } from 'lucide-react';
import BaseNode from './BaseNode';

const COLOR = 'var(--node-output)';

const OutputNode: React.FC<NodeProps> = ({ data, selected }) => {
  const format = (data.format as string) || 'text';

  return (
    <BaseNode
      label={(data.label as string) || 'Output'}
      accentColor={COLOR}
      icon={<FileText className="w-3 h-3" />}
      selected={selected}
    >
      <div className="flex items-center gap-2">
        <p className="node-field-label">Format</p>
        <span
          className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider"
          style={{
            background: format === 'json' ? 'rgba(234,179,8,0.15)' : 'rgba(249,115,22,0.15)',
            color: format === 'json' ? '#facc15' : 'var(--node-output)',
          }}
        >
          {format}
        </span>
      </div>
    </BaseNode>
  );
};

export default OutputNode;
