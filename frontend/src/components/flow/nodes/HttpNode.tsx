import React from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';

const HTTP_COLOR = '#ec4899';

const methodColors: Record<string, string> = {
  GET: 'bg-green-100 text-green-700',
  POST: 'bg-blue-100 text-blue-700',
  PUT: 'bg-amber-100 text-amber-700',
  PATCH: 'bg-orange-100 text-orange-700',
  DELETE: 'bg-red-100 text-red-700',
};

const HttpNode: React.FC<NodeProps> = ({ data, selected }) => {
  const method = ((data.method as string) || 'GET').toUpperCase();
  const url = (data.url as string) || '';
  const truncatedUrl = url.length > 30 ? url.slice(0, 30) + '...' : url;

  return (
    <BaseNode label={data.label as string || 'HTTP Request'} color={HTTP_COLOR} selected={selected}>
      <div className="flex items-center gap-2">
        <span
          className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
            methodColors[method] || 'bg-gray-100 text-gray-700'
          }`}
        >
          {method}
        </span>
        {url ? (
          <span className="text-xs text-gray-600 truncate font-mono">{truncatedUrl}</span>
        ) : (
          <span className="text-xs text-gray-400 italic">No URL set</span>
        )}
      </div>
    </BaseNode>
  );
};

export default HttpNode;
