import React from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';

const TRANSFORM_COLOR = '#06b6d4';

const TransformNode: React.FC<NodeProps> = ({ data, selected }) => {
  const transformation = (data.transformation as string) || 'passthrough';

  const transformLabels: Record<string, string> = {
    passthrough: 'Passthrough',
    uppercase: 'Uppercase',
    lowercase: 'Lowercase',
    trim: 'Trim',
    split: 'Split',
    join: 'Join',
    extract_field: 'Extract Field',
    parse_json: 'Parse JSON',
    stringify: 'Stringify',
  };

  return (
    <BaseNode label={data.label as string || 'Transform'} color={TRANSFORM_COLOR} selected={selected}>
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-medium text-gray-500 uppercase">Type</span>
        <span className="text-xs font-semibold text-cyan-700 bg-cyan-50 px-2 py-0.5 rounded">
          {transformLabels[transformation] || transformation}
        </span>
      </div>
    </BaseNode>
  );
};

export default TransformNode;
