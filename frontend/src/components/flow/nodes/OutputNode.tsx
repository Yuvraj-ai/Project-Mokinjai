import React from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';

const OUTPUT_COLOR = '#ef4444';

const OutputNode: React.FC<NodeProps> = ({ data, selected }) => {
  const format = (data.format as string) || 'text';

  return (
    <BaseNode label={data.label as string || 'Output'} color={OUTPUT_COLOR} selected={selected}>
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-medium text-gray-500 uppercase">Format</span>
        <span
          className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
            format === 'json'
              ? 'bg-amber-100 text-amber-700'
              : 'bg-gray-100 text-gray-700'
          }`}
        >
          {format.toUpperCase()}
        </span>
      </div>
    </BaseNode>
  );
};

export default OutputNode;
