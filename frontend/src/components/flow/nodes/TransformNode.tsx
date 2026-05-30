import React from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';

const TRANSFORM_COLOR = '#0E7C86';

const TransformNode: React.FC<NodeProps> = ({ id, data, selected }) => {
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
    <BaseNode id={id} label={data.label as string || 'Transform'} color={TRANSFORM_COLOR} selected={selected}>
      <div className="flex items-center gap-1.5">
        <span className="font-body text-[9px] font-semibold text-ink-300 dark:text-ink-400 uppercase tracking-wider">Type</span>
        <span
          className="font-body text-[10px] font-semibold px-1.5 py-0.5 rounded"
          style={{ backgroundColor: `${TRANSFORM_COLOR}15`, color: TRANSFORM_COLOR }}
        >
          {transformLabels[transformation] || transformation}
        </span>
      </div>
    </BaseNode>
  );
};

export default TransformNode;
