import React from 'react';
import { NodeProps } from '@xyflow/react';
import { BookOpen } from 'lucide-react';
import BaseNode from './BaseNode';

const COLOR = 'var(--node-knowledge)';

const KnowledgeNode: React.FC<NodeProps> = ({ data, selected }) => {
  const kbName = (data.knowledgeBaseName as string) || (data.knowledgeBaseId as string) || '';
  const topK = (data.topK as number) ?? 5;

  return (
    <BaseNode
      label={(data.label as string) || 'Knowledge Base'}
      accentColor={COLOR}
      icon={<BookOpen className="w-3 h-3" />}
      selected={selected}
    >
      <div className="space-y-1.5">
        <div className="flex items-center gap-2 min-w-0">
          {kbName ? (
            <span className="text-[10px] font-medium truncate" style={{ color: 'var(--text-secondary)' }}>
              {kbName}
            </span>
          ) : (
            <span className="text-[10px] italic" style={{ color: 'var(--text-disabled)' }}>No KB selected</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <p className="node-field-label">Top K</p>
          <span
            className="text-[10px] font-bold px-1.5 py-0.5 rounded"
            style={{ background: 'rgba(20,184,166,0.15)', color: 'var(--node-knowledge)' }}
          >
            {topK}
          </span>
        </div>
      </div>
    </BaseNode>
  );
};

export default KnowledgeNode;
