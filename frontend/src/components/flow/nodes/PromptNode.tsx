import React from 'react';
import { NodeProps } from '@xyflow/react';
import { MessageSquare } from 'lucide-react';
import BaseNode from './BaseNode';

const COLOR = 'var(--node-prompt)';

const PromptNode: React.FC<NodeProps> = ({ data, selected }) => {
  const template = (data.template as string) || '';
  const truncated = template.length > 80 ? template.slice(0, 80) + '…' : template;

  return (
    <BaseNode
      label={(data.label as string) || 'Prompt'}
      accentColor={COLOR}
      icon={<MessageSquare className="w-3 h-3" />}
      selected={selected}
    >
      {template ? (
        <p
          className="text-[10px] font-mono leading-relaxed break-words rounded px-2 py-1.5"
          style={{
            color: 'var(--text-secondary)',
            background: 'var(--bg-overlay)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          {truncated}
        </p>
      ) : (
        <p className="text-[10px] italic" style={{ color: 'var(--text-disabled)' }}>
          No template configured
        </p>
      )}
    </BaseNode>
  );
};

export default PromptNode;
