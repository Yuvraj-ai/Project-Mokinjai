import React from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';
import { BookOpen } from 'lucide-react';

const KNOWLEDGE_COLOR = '#14b8a6';

const KnowledgeNode: React.FC<NodeProps> = ({ data, selected }) => {
  const kbName = (data.knowledgeBaseName as string) || (data.knowledgeBaseId as string) || '';
  const topK = (data.topK as number) ?? 5;

  return (
    <BaseNode label={data.label as string || 'Knowledge Base'} color={KNOWLEDGE_COLOR} selected={selected}>
      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5">
          <BookOpen className="w-3 h-3 text-teal-600" />
          {kbName ? (
            <span className="text-xs font-medium text-gray-700 truncate max-w-[160px]">
              {kbName}
            </span>
          ) : (
            <span className="text-xs text-gray-400 italic">No KB selected</span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-medium text-gray-500 uppercase">Top K</span>
          <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-1.5 py-0.5 rounded">
            {topK}
          </span>
        </div>
      </div>
    </BaseNode>
  );
};

export default KnowledgeNode;
