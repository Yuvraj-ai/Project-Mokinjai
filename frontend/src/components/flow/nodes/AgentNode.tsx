import React from 'react';
import { NodeProps } from '@xyflow/react';
import { Bot } from 'lucide-react';
import BaseNode from './BaseNode';
import useWorkflowStore from '../../../store/workflowStore';

const COLOR = 'var(--node-agent)';

const AgentNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);

  const provider    = (data.provider as string) || 'openai';
  const model       = (data.model as string) || '';
  const temperature = (data.temperature as number) ?? 0.7;

  return (
    <BaseNode
      label={(data.label as string) || 'Agent'}
      accentColor={COLOR}
      icon={<Bot className="w-3 h-3" />}
      selected={selected}
    >
      <div className="space-y-2">
        <div>
          <p className="node-field-label">Provider</p>
          <select
            value={provider}
            onChange={(e) => updateNodeData(id, { provider: e.target.value })}
            className="node-select"
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google Gemini</option>
          </select>
        </div>

        <div>
          <p className="node-field-label">Model</p>
          <input
            type="text"
            value={model}
            onChange={(e) => updateNodeData(id, { model: e.target.value })}
            placeholder={provider === 'openai' ? 'gpt-4o' : provider === 'anthropic' ? 'claude-3-5-sonnet-20241022' : 'gemini-2.0-flash'}
            className="node-input"
          />
        </div>

        <div>
          <p className="node-field-label">Temperature: {temperature.toFixed(1)}</p>
          <div
            className="w-full rounded-full h-1.5 mt-1 overflow-hidden"
            style={{ background: 'var(--bg-overlay)' }}
          >
            <div
              className="h-1.5 rounded-full transition-all"
              style={{
                width: `${temperature * 100}%`,
                background: `linear-gradient(90deg, var(--node-agent), #7c3aed)`,
              }}
            />
          </div>
        </div>
      </div>
    </BaseNode>
  );
};

export default AgentNode;
