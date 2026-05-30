import React from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';
import { BookOpen } from 'lucide-react';

const KNOWLEDGE_COLOR = '#1A756F';

const KnowledgeNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const kbName = (data.knowledgeBaseName as string) || (data.knowledgeBaseId as string) || '';
  const topK = (data.topK as number) ?? 5;

  return (
    <BaseNode id={id} label={data.label as string || 'Knowledge Base'} color={KNOWLEDGE_COLOR} selected={selected}>
      <div className="space-y-1">
        <div className="flex items-center gap-1.5">
          <BookOpen className="w-3 h-3 text-ink-300 dark:text-ink-400" />
          {kbName ? (
            <span className="font-body text-[10px] font-medium text-ink-500 dark:text-cream-200 truncate max-w-[140px]">
              {kbName}
            </span>
          ) : (
            <span className="font-body text-[10px] text-ink-300 dark:text-ink-400 italic">No KB selected</span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="font-body text-[9px] font-semibold text-ink-300 dark:text-ink-400 uppercase tracking-wider">Top K</span>
          <span
            className="font-body text-[10px] font-semibold px-1.5 py-0.5 rounded"
            style={{ backgroundColor: `${KNOWLEDGE_COLOR}15`, color: KNOWLEDGE_COLOR }}
          >
            {topK}
          </span>
        </div>
      </div>
    </BaseNode>
  );
};

export default KnowledgeNode;
