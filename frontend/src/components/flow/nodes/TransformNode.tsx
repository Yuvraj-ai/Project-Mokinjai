import React from 'react';
import { NodeProps } from '@xyflow/react';
import { Shuffle } from 'lucide-react';
import BaseNode from './BaseNode';

const COLOR = 'var(--node-transform)';

const transformLabels: Record<string, string> = {
  passthrough:   'Passthrough',
  uppercase:     'Uppercase',
  lowercase:     'Lowercase',
  trim:          'Trim',
  split:         'Split',
  join:          'Join',
  extract_field: 'Extract Field',
  parse_json:    'Parse JSON',
  stringify:     'Stringify',
};

const TransformNode: React.FC<NodeProps> = ({ data, selected }) => {
  const transformation = (data.transformation as string) || 'passthrough';

  return (
    <BaseNode
      label={(data.label as string) || 'Transform'}
      accentColor={COLOR}
      icon={<Shuffle className="w-3 h-3" />}
      selected={selected}
    >
      <div className="flex items-center gap-2">
        <p className="node-field-label">Type</p>
        <span
          className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wide"
          style={{ background: 'rgba(6,182,212,0.15)', color: 'var(--node-transform)' }}
        >
          {transformLabels[transformation] || transformation}
        </span>
      </div>
    </BaseNode>
  );
};

export default TransformNode;
