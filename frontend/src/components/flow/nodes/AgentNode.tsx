import React from 'react';
import { NodeProps } from '@xyflow/react';
import BaseNode from './BaseNode';
import useWorkflowStore from '../../../store/workflowStore';
import { FileText } from 'lucide-react';

const AGENT_COLOR = '#7B2D8B';

const AgentNode: React.FC<NodeProps> = ({ id, data, selected }) => {
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);

  const provider = (data.provider as string) || 'openai';
  const model = (data.model as string) || '';
  const temperature = (data.temperature as number) ?? 0.7;
  const promptName = (data.promptName as string) || '';
  const systemPrompt = (data.systemPrompt as string) || '';

  return (
    <BaseNode id={id} label={data.label as string || 'Agent'} color={AGENT_COLOR} selected={selected}>
      <div className="space-y-1.5">
        <div>
          <label className="font-body text-[9px] font-semibold text-ink-muted uppercase tracking-wider">Provider</label>
          <select
            value={provider}
            onChange={(e) => updateNodeData(id, { provider: e.target.value })}
            className="w-full font-body text-[10px] border border-line rounded px-2 py-1 mt-0.5 bg-surface dark:bg-surface focus:outline-none focus:ring-1 focus:ring-[#7B2D8B]/40 text-ink dark:text-ink"
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="gemini">Gemini</option>
          </select>
        </div>

        <div>
          <label className="font-body text-[9px] font-semibold text-ink-muted uppercase tracking-wider">Model</label>
          <input
            type="text"
            value={model}
            onChange={(e) => updateNodeData(id, { model: e.target.value })}
            placeholder="e.g. gpt-4o"
            className="w-full font-body text-[10px] border border-line rounded px-2 py-1 mt-0.5 bg-surface dark:bg-surface focus:outline-none focus:ring-1 focus:ring-[#7B2D8B]/40 text-ink dark:text-ink placeholder:text-ink-muted dark:placeholder:text-ink-muted"
          />
        </div>

        {promptName ? (
          <div className="flex items-center gap-1.5 px-2 py-1 bg-surface-muted rounded border border-line">
            <FileText className="w-3 h-3 text-ink-muted shrink-0" />
            <span className="font-body text-[9px] font-medium text-ink-muted truncate">{promptName}</span>
          </div>
        ) : systemPrompt ? (
          <div className="px-2 py-1 bg-surface-muted rounded border border-line">
            <span className="font-mono text-[8px] text-ink-muted line-clamp-2">{systemPrompt}</span>
          </div>
        ) : null}

        <div>
          <label className="font-body text-[9px] font-semibold text-ink-muted uppercase tracking-wider">
            Temp: {temperature.toFixed(1)}
          </label>
          <div className="w-full bg-surface-muted rounded-full h-1 mt-1">
            <div
              className="h-1 rounded-full transition-all duration-200"
              style={{ width: `${temperature * 100}%`, backgroundColor: AGENT_COLOR }}
            />
          </div>
        </div>
      </div>
    </BaseNode>
  );
};

export default AgentNode;
