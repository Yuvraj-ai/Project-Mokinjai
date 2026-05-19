import React from 'react';
import { NodeProps } from '@xyflow/react';
import { ArrowRightFromLine } from 'lucide-react';
import BaseNode from './BaseNode';
import useWorkflowStore from '../../../store/workflowStore';

const COLOR = 'var(--node-input)';

const InputNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);
  const value = (data.value as string) || '';

  return (
    <BaseNode
      label={(data.label as string) || 'Input'}
      accentColor={COLOR}
      icon={<ArrowRightFromLine className="w-3 h-3" />}
      selected={selected}
    >
      <div className="space-y-2">
        <div>
          <p className="node-field-label">Default Value</p>
          <input
            type="text"
            value={value}
            onChange={(e) => updateNodeData(id, { value: e.target.value })}
            placeholder="Enter input value…"
            className="node-input"
          />
        </div>
      </div>
    </BaseNode>
  );
};

export default InputNode;
