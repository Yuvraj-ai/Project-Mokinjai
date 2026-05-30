import React, { useCallback } from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';
import useWorkflowStore from '../../../store/workflowStore';

const INPUT_COLOR = '#2D6A4F';

const InputNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      updateNodeData(id, { value: e.target.value });
    },
    [id, updateNodeData]
  );

  return (
    <BaseNode id={id} label={data.label as string || 'Input'} color={INPUT_COLOR} selected={selected}>
      <textarea
        value={(data.value as string) || ''}
        onChange={handleChange}
        placeholder="Enter input..."
        className="w-full font-mono text-[10px] border border-ink-100/60 dark:border-ink-600 rounded px-2 py-1 resize-none focus:outline-none focus:ring-1 focus:ring-[#2D6A4F]/40 bg-ink-50/50 dark:bg-ink-700/50 text-ink-600 dark:text-cream-200 placeholder:text-ink-300/60 dark:placeholder:text-ink-400"
        rows={2}
      />
    </BaseNode>
  );
};

export default InputNode;
