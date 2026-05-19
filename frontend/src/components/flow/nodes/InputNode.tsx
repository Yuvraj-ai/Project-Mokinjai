import React, { useCallback } from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';
import useWorkflowStore from '../../../store/workflowStore';

const INPUT_COLOR = '#22c55e';

const InputNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      updateNodeData(id, { value: e.target.value });
    },
    [id, updateNodeData]
  );

  return (
    <BaseNode label={data.label as string || 'Input'} color={INPUT_COLOR} selected={selected}>
      <textarea
        value={(data.value as string) || ''}
        onChange={handleChange}
        placeholder="Enter initial input value..."
        className="w-full text-xs border border-gray-200 rounded px-2 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-green-400 bg-gray-50"
        rows={3}
      />
    </BaseNode>
  );
};

export default InputNode;
