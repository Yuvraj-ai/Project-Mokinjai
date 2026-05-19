import React from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';
import useWorkflowStore from '../../../store/workflowStore';

const AGENT_COLOR = '#8b5cf6';

const AgentNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);

  const provider = (data.provider as string) || 'openai';
  const model = (data.model as string) || '';
  const temperature = (data.temperature as number) ?? 0.7;

  return (
    <BaseNode label={data.label as string || 'Agent'} color={AGENT_COLOR} selected={selected}>
      <div className="space-y-2">
        <div>
          <label className="text-[10px] font-medium text-gray-500 uppercase">Provider</label>
          <select
            value={provider}
            onChange={(e) => updateNodeData(id, { provider: e.target.value })}
            className="w-full text-xs border border-gray-200 rounded px-2 py-1 mt-0.5 bg-gray-50 focus:outline-none focus:ring-1 focus:ring-purple-400"
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </div>

        <div>
          <label className="text-[10px] font-medium text-gray-500 uppercase">Model</label>
          <input
            type="text"
            value={model}
            onChange={(e) => updateNodeData(id, { model: e.target.value })}
            placeholder="e.g. gpt-4o"
            className="w-full text-xs border border-gray-200 rounded px-2 py-1 mt-0.5 bg-gray-50 focus:outline-none focus:ring-1 focus:ring-purple-400"
          />
        </div>

        <div>
          <label className="text-[10px] font-medium text-gray-500 uppercase">
            Temperature: {temperature.toFixed(1)}
          </label>
          <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
            <div
              className="bg-purple-500 h-1.5 rounded-full transition-all"
              style={{ width: `${temperature * 100}%` }}
            />
          </div>
        </div>
      </div>
    </BaseNode>
  );
};

export default AgentNode;
