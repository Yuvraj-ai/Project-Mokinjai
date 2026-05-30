import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';

const PROMPT_COLOR = '#264653';

const PromptNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const promptName = (data.promptName as string) || '';
  const template = (data.template as string) || '';
  const variables = (data.variables as string[]) || [];

  const displayText = promptName
    ? `Linked: ${promptName}`
    : template.length > 60
      ? template.slice(0, 60) + '...'
      : template;

  return (
    <BaseNode id={id} label={data.label as string || 'Prompt'} color={PROMPT_COLOR} selected={selected}>
      <div className="space-y-1">
        {promptName ? (
          <p className="font-body text-[10px] text-accent-warm font-medium truncate">{displayText}</p>
        ) : template ? (
          <p className="font-mono text-[10px] text-ink-400 dark:text-ink-300 bg-ink-50/50 dark:bg-ink-700/50 border border-ink-100/60 dark:border-ink-600 rounded px-2 py-1 leading-relaxed whitespace-pre-wrap break-words">
            {displayText}
          </p>
        ) : (
          <p className="font-body text-[10px] text-ink-300 dark:text-ink-400 italic">No template configured</p>
        )}
      </div>

      {/* Variable input handles */}
      {variables.map((varName, i) => (
        <Handle
          key={varName}
          type="target"
          position={Position.Left}
          id={`var-${varName}`}
          style={{ top: `${30 + (i + 1) * 25}%` }}
          className="!w-2.5 !h-2.5 !bg-ink-200 !border-2 !border-white !-left-1.5"
        />
      ))}
      {variables.length > 0 && variables.map((varName, i) => (
        <span
          key={`label-${varName}`}
          className="absolute text-[8px] font-mono text-ink-300 dark:text-ink-400 pointer-events-none"
          style={{ left: -4, top: `${30 + (i + 1) * 25 - 3}%`, transform: 'translateX(-100%)' }}
        >
          {`{${varName}}`}
        </span>
      ))}
    </BaseNode>
  );
};

export default PromptNode;
