import React from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';

const PROMPT_COLOR = '#3b82f6';

const PromptNode: React.FC<NodeProps> = ({ data, selected }) => {
  const template = (data.template as string) || '';
  const truncated = template.length > 80 ? template.slice(0, 80) + '...' : template;

  return (
    <BaseNode label={data.label as string || 'Prompt'} color={PROMPT_COLOR} selected={selected}>
      <div className="space-y-1">
        {template ? (
          <p className="text-xs text-gray-600 bg-blue-50 rounded px-2 py-1.5 font-mono leading-relaxed whitespace-pre-wrap break-words">
            {truncated}
          </p>
        ) : (
          <p className="text-xs text-gray-400 italic">No template configured</p>
        )}
      </div>
    </BaseNode>
  );
};

export default PromptNode;
