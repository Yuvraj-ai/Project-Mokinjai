import React from 'react';
import { NodeProps } from '@xyflow/react';
import { Globe } from 'lucide-react';
import BaseNode from './BaseNode';

const COLOR = 'var(--node-http)';

const methodStyle: Record<string, { bg: string; color: string }> = {
  GET:    { bg: 'rgba(34,197,94,0.15)',  color: '#4ade80' },
  POST:   { bg: 'rgba(59,130,246,0.15)', color: '#60a5fa' },
  PUT:    { bg: 'rgba(234,179,8,0.15)',  color: '#facc15' },
  PATCH:  { bg: 'rgba(249,115,22,0.15)', color: '#fb923c' },
  DELETE: { bg: 'rgba(239,68,68,0.15)',  color: '#f87171' },
};

const HttpNode: React.FC<NodeProps> = ({ data, selected }) => {
  const method = ((data.method as string) || 'GET').toUpperCase();
  const url = (data.url as string) || '';
  const truncatedUrl = url.length > 28 ? url.slice(0, 28) + '…' : url;
  const ms = methodStyle[method] || { bg: 'rgba(100,116,139,0.15)', color: 'var(--text-muted)' };

  return (
    <BaseNode
      label={(data.label as string) || 'HTTP Request'}
      accentColor={COLOR}
      icon={<Globe className="w-3 h-3" />}
      selected={selected}
    >
      <div className="flex items-center gap-2">
        <span
          className="text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-widest flex-shrink-0"
          style={{ background: ms.bg, color: ms.color }}
        >
          {method}
        </span>
        {url ? (
          <span className="text-[10px] truncate font-mono" style={{ color: 'var(--text-secondary)' }}>
            {truncatedUrl}
          </span>
        ) : (
          <span className="text-[10px] italic" style={{ color: 'var(--text-disabled)' }}>No URL set</span>
        )}
      </div>
    </BaseNode>
  );
};

export default HttpNode;
