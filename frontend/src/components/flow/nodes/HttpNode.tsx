import React from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';

const HTTP_COLOR = '#8B2252';

const HttpNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const method = ((data.method as string) || 'GET').toUpperCase();
  const url = (data.url as string) || '';
  const truncatedUrl = url.length > 30 ? url.slice(0, 30) + '...' : url;

  return (
    <BaseNode id={id} label={data.label as string || 'HTTP Request'} color={HTTP_COLOR} selected={selected}>
      <div className="flex items-center gap-1.5">
        <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-ink-50/50 dark:bg-ink-700/50 text-ink-600 dark:text-cream-200">
          {method}
        </span>
        {url ? (
          <span className="font-mono text-[10px] text-ink-400 dark:text-ink-300 truncate">{truncatedUrl}</span>
        ) : (
          <span className="font-body text-[10px] text-ink-300 dark:text-ink-400 italic">No URL set</span>
        )}
      </div>
    </BaseNode>
  );
};

export default HttpNode;
