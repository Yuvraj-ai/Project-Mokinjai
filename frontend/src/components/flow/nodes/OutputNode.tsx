import React from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';

const OUTPUT_COLOR = '#9B2226';

const OutputNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const format = (data.format as string) || 'text';

  return (
    <BaseNode id={id} label={data.label as string || 'Output'} color={OUTPUT_COLOR} selected={selected}>
      <div className="flex items-center gap-1.5">
        <span className="font-body text-[9px] font-semibold text-ink-300 dark:text-ink-400 uppercase tracking-wider">Format</span>
        <span
          className={`font-mono text-[10px] font-semibold px-1.5 py-0.5 rounded ${
            format === 'json'
              ? 'bg-[#C4956A]/15 text-[#C4956A]'
              : 'bg-ink-50/50 dark:bg-ink-700/50 text-ink-500 dark:text-cream-200'
          }`}
        >
          {format.toUpperCase()}
        </span>
      </div>
    </BaseNode>
  );
};

export default OutputNode;
