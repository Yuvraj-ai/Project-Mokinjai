import React from 'react';
import useWorkflowStore from '../../../store/workflowStore';
import { X } from 'lucide-react';

const PropertiesPanel: React.FC = () => {
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);
  const setSelectedNodeId = useWorkflowStore((s) => s.setSelectedNodeId);
  const nodes = useWorkflowStore((s) => s.nodes);
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  if (!selectedNode) {
    return (
      <div className="w-64 bg-white dark:bg-ink-800 border-l border-ink-100/60 dark:border-ink-700/60 h-full flex items-center justify-center">
        <p className="font-body text-xs text-ink-300 dark:text-ink-400 italic">Select a node to edit</p>
      </div>
    );
  }

  const { data, type } = selectedNode;

  const update = (key: string, value: unknown) => {
    updateNodeData(selectedNode.id, { [key]: value });
  };

  const renderLabel = (text: string) => (
    <label className="block font-body text-[9px] font-semibold text-ink-300 dark:text-ink-400 uppercase tracking-wider mb-1">
      {text}
    </label>
  );

  const renderInput = (key: string, label: string, placeholder?: string, inputType = 'text') => (
    <div>
      {renderLabel(label)}
      <input
        type={inputType}
        value={(data[key] as string) || ''}
        onChange={(e) => update(key, inputType === 'number' ? Number(e.target.value) : e.target.value)}
        placeholder={placeholder}
        className="w-full font-body text-[11px] border border-ink-100/60 dark:border-ink-600 rounded px-2.5 py-1.5 bg-ink-50/30 dark:bg-ink-700/50 text-ink-600 dark:text-cream-200 placeholder-ink-300/50 focus:outline-none focus:ring-1 focus:ring-accent-warm/40 focus:border-accent-warm transition-all duration-150"
      />
    </div>
  );

  const renderTextarea = (key: string, label: string, placeholder?: string, rows = 3) => (
    <div>
      {renderLabel(label)}
      <textarea
        value={(data[key] as string) || ''}
        onChange={(e) => update(key, e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="w-full font-body text-[11px] border border-ink-100/60 dark:border-ink-600 rounded px-2.5 py-1.5 bg-ink-50/30 dark:bg-ink-700/50 text-ink-600 dark:text-cream-200 placeholder-ink-300/50 dark:placeholder:text-ink-400 focus:outline-none focus:ring-1 focus:ring-accent-warm/40 focus:border-accent-warm resize-none font-mono transition-all duration-150"
      />
    </div>
  );

  const renderSelect = (key: string, label: string, options: { value: string; label: string }[]) => (
    <div>
      {renderLabel(label)}
      <select
        value={(data[key] as string) || options[0]?.value || ''}
        onChange={(e) => update(key, e.target.value)}
        className="w-full font-body text-[11px] border border-ink-100/60 dark:border-ink-600 rounded px-2.5 py-1.5 bg-ink-50/30 dark:bg-ink-700/50 text-ink-600 dark:text-cream-200 focus:outline-none focus:ring-1 focus:ring-accent-warm/40 focus:border-accent-warm transition-all duration-150"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );

  const renderSlider = (key: string, label: string, min: number, max: number, step: number) => {
    const value = (data[key] as number) ?? min;
    return (
      <div>
        {renderLabel(`${label}: ${value}`)}
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => update(key, parseFloat(e.target.value))}
          className="w-full accent-[#C4956A]"
        />
      </div>
    );
  };

  const renderFields = () => {
    switch (type) {
      case 'agent':
        return (
          <>
            {renderSelect('provider', 'Provider', [
              { value: 'openai', label: 'OpenAI' },
              { value: 'anthropic', label: 'Anthropic' },
              { value: 'gemini', label: 'Gemini' },
            ])}
            {renderInput('model', 'Model', 'e.g. gpt-4o')}
            {renderTextarea('systemPrompt', 'System Prompt', 'Enter system prompt...', 5)}
            {renderSlider('temperature', 'Temperature', 0, 2, 0.1)}
            {renderInput('maxTokens', 'Max Tokens', '4096', 'number')}
          </>
        );

      case 'prompt':
        return (
          <>
            {renderTextarea('template', 'Template', 'Enter prompt template with {{variables}}...', 6)}
            <div>
              {renderLabel('Variables')}
              <div className="space-y-1">
                {((data.variables as string[]) || []).map((v: string, i: number) => (
                  <div key={i} className="flex items-center gap-1">
                    <input
                      type="text"
                      value={v}
                      onChange={(e) => {
                        const vars = [...((data.variables as string[]) || [])];
                        vars[i] = e.target.value;
                        update('variables', vars);
                      }}
                      className="flex-1 font-body text-[11px] border border-ink-100/60 dark:border-ink-600 rounded px-2 py-1 bg-ink-50/30 dark:bg-ink-700/50 text-ink-600 dark:text-cream-200 focus:outline-none focus:ring-1 focus:ring-accent-warm/40 transition-all duration-150"
                    />
                    <button
                      onClick={() => {
                        const vars = ((data.variables as string[]) || []).filter(
                          (_: string, idx: number) => idx !== i
                        );
                        update('variables', vars);
                      }}
                      className="text-ink-300 hover:text-status-error p-0.5 transition-colors duration-150"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                <button
                  onClick={() =>
                    update('variables', [...((data.variables as string[]) || []), ''])
                  }
                  className="font-body text-[10px] text-accent hover:text-accent-warm font-semibold tracking-wide transition-colors duration-150"
                >
                  + Add Variable
                </button>
              </div>
            </div>
          </>
        );

      case 'output':
        return renderSelect('format', 'Format', [
          { value: 'text', label: 'Text' },
          { value: 'json', label: 'JSON' },
        ]);

      case 'input':
        return renderTextarea('value', 'Initial Value', 'Enter input value...', 5);

      case 'conditional':
        return (
          <>
            {renderSelect('conditionType', 'Condition Type', [
              { value: 'equals', label: 'Equals' },
              { value: 'not_equals', label: 'Not Equals' },
              { value: 'contains', label: 'Contains' },
              { value: 'not_contains', label: 'Not Contains' },
              { value: 'greater_than', label: 'Greater Than' },
              { value: 'less_than', label: 'Less Than' },
              { value: 'regex', label: 'Regex Match' },
              { value: 'is_empty', label: 'Is Empty' },
            ])}
            {renderInput('conditionValue', 'Condition Value', 'Value to compare against')}
          </>
        );

      case 'transform':
        return (
          <>
            {renderSelect('transformation', 'Transformation', [
              { value: 'passthrough', label: 'Passthrough' },
              { value: 'uppercase', label: 'Uppercase' },
              { value: 'lowercase', label: 'Lowercase' },
              { value: 'trim', label: 'Trim' },
              { value: 'split', label: 'Split' },
              { value: 'join', label: 'Join' },
              { value: 'extract_field', label: 'Extract Field' },
              { value: 'parse_json', label: 'Parse JSON' },
              { value: 'stringify', label: 'Stringify' },
            ])}
            {renderInput('field', 'Field Path', 'e.g. data.results[0].name')}
            {renderInput('delimiter', 'Delimiter', 'e.g. comma, newline')}
          </>
        );

      case 'http_request':
        return (
          <>
            {renderSelect('method', 'Method', [
              { value: 'GET', label: 'GET' },
              { value: 'POST', label: 'POST' },
              { value: 'PUT', label: 'PUT' },
              { value: 'PATCH', label: 'PATCH' },
              { value: 'DELETE', label: 'DELETE' },
            ])}
            {renderInput('url', 'URL', 'https://api.example.com/endpoint')}
            {renderTextarea('headers', 'Headers (JSON)', '{"Authorization": "Bearer ..."}', 3)}
            {renderTextarea('body', 'Body', 'Request body...', 4)}
          </>
        );

      case 'knowledge':
        return (
          <>
            {renderInput('knowledgeBaseId', 'Knowledge Base ID', 'Enter KB ID')}
            {renderInput('topK', 'Top K Results', '5', 'number')}
            {renderInput('threshold', 'Similarity Threshold', '0.7', 'number')}
          </>
        );

      default:
        return <p className="font-body text-xs text-ink-300 italic">No properties for this node type.</p>;
    }
  };

  return (
    <div className="w-64 bg-white dark:bg-ink-800 border-l border-ink-100/60 dark:border-ink-700/60 h-full overflow-y-auto">
      <div className="p-3 border-b border-ink-100/60 dark:border-ink-700/60 flex items-center justify-between">
        <div>
          <h2 className="font-body text-xs font-semibold text-ink-700 dark:text-cream-200">Properties</h2>
          <p className="font-body text-[10px] text-ink-300 dark:text-ink-400 mt-0.5 capitalize">{type} node</p>
        </div>
        <button
          onClick={() => setSelectedNodeId(null)}
          className="text-ink-300 dark:text-ink-400 hover:text-ink-500 p-1 rounded hover:bg-ink-50 dark:hover:bg-ink-700 transition-all duration-150"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="p-3 space-y-3">
        {renderInput('label', 'Label', 'Node label')}
        <div className="editorial-rule" />
        {renderFields()}
      </div>
    </div>
  );
};

export default PropertiesPanel;
