import React from 'react';
import useWorkflowStore from '../../../store/workflowStore';
import { X, Trash2 } from 'lucide-react';

const PropertiesPanel: React.FC = () => {
  const selectedNodeId  = useWorkflowStore((s) => s.selectedNodeId);
  const setSelectedNodeId = useWorkflowStore((s) => s.setSelectedNodeId);
  const nodes           = useWorkflowStore((s) => s.nodes);
  const updateNodeData  = useWorkflowStore((s) => s.updateNodeData);
  const removeNode      = useWorkflowStore((s) => s.removeNode);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  if (!selectedNode) return null;

  const { data, type } = selectedNode;
  const update = (key: string, value: unknown) => updateNodeData(selectedNode.id, { [key]: value });

  /* ── Style helpers ────────────────────────────── */
  const fieldLabel = (text: string) => (
    <label
      className="block text-[10px] font-bold uppercase tracking-widest mb-1"
      style={{ color: 'var(--text-disabled)' }}
    >
      {text}
    </label>
  );

  const inputCls = `
    w-full text-xs rounded-lg px-2.5 py-1.5 outline-none transition-all
  `;
  const inputStyle = {
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border-default)',
    color: 'var(--text-primary)',
  };
  const inputFocusHandlers = {
    onFocus: (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      e.currentTarget.style.borderColor = 'var(--accent-mid)';
      e.currentTarget.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.15)';
    },
    onBlur: (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      e.currentTarget.style.borderColor = 'var(--border-default)';
      e.currentTarget.style.boxShadow = 'none';
    },
  };

  const renderInput = (key: string, label: string, placeholder?: string, inputType = 'text') => (
    <div key={key}>
      {fieldLabel(label)}
      <input
        type={inputType}
        value={(data[key] as string) || ''}
        onChange={(e) => update(key, inputType === 'number' ? Number(e.target.value) : e.target.value)}
        placeholder={placeholder}
        className={inputCls}
        style={inputStyle}
        {...inputFocusHandlers}
      />
    </div>
  );

  const renderTextarea = (key: string, label: string, placeholder?: string, rows = 4) => (
    <div key={key}>
      {fieldLabel(label)}
      <textarea
        value={(data[key] as string) || ''}
        onChange={(e) => update(key, e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className={`${inputCls} font-mono resize-none leading-relaxed`}
        style={inputStyle}
        {...inputFocusHandlers}
      />
    </div>
  );

  const renderSelect = (key: string, label: string, options: { value: string; label: string }[]) => (
    <div key={key}>
      {fieldLabel(label)}
      <select
        value={(data[key] as string) || options[0]?.value || ''}
        onChange={(e) => update(key, e.target.value)}
        className={inputCls}
        style={{ ...inputStyle, appearance: 'none' }}
        {...inputFocusHandlers}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} style={{ background: 'var(--bg-elevated)' }}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );

  const renderSlider = (key: string, label: string, min: number, max: number, step: number) => {
    const value = (data[key] as number) ?? min;
    return (
      <div key={key}>
        {fieldLabel(`${label}: ${value}`)}
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => update(key, parseFloat(e.target.value))}
          className="w-full"
          style={{ accentColor: 'var(--accent-mid)' }}
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
              { value: 'google', label: 'Google Gemini' },
            ])}
            {renderInput('model', 'Model', 'e.g. gpt-4o, claude-3-5-sonnet, gemini-2.0-flash')}
            {renderTextarea('systemPrompt', 'System Prompt', 'You are a helpful assistant…', 5)}
            {renderSlider('temperature', 'Temperature', 0, 2, 0.1)}
            {renderInput('maxTokens', 'Max Tokens', '4096', 'number')}
          </>
        );

      case 'prompt':
        return (
          <>
            {renderTextarea('template', 'Template', 'Enter prompt with {{variable}} syntax…', 6)}
            <div>
              {fieldLabel('Variables')}
              <div className="space-y-1.5">
                {((data.variables as string[]) || []).map((v: string, i: number) => (
                  <div key={i} className="flex items-center gap-1.5">
                    <input
                      type="text"
                      value={v}
                      onChange={(e) => {
                        const vars = [...((data.variables as string[]) || [])];
                        vars[i] = e.target.value;
                        update('variables', vars);
                      }}
                      className={`flex-1 ${inputCls}`}
                      style={inputStyle}
                      {...inputFocusHandlers}
                    />
                    <button
                      onClick={() => {
                        const vars = ((data.variables as string[]) || []).filter(
                          (_: string, idx: number) => idx !== i
                        );
                        update('variables', vars);
                      }}
                      className="w-6 h-6 flex items-center justify-center rounded transition-colors flex-shrink-0"
                      style={{ color: '#f87171' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.1)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                <button
                  onClick={() => update('variables', [...((data.variables as string[]) || []), ''])}
                  className="text-[10px] font-semibold transition-colors"
                  style={{ color: 'var(--accent-mid)' }}
                >
                  + Add Variable
                </button>
              </div>
            </div>
          </>
        );

      case 'input':
        return renderTextarea('value', 'Initial Value', 'Enter input value…', 5);

      case 'output':
        return renderSelect('format', 'Format', [
          { value: 'text', label: 'Text' },
          { value: 'json', label: 'JSON' },
        ]);

      case 'conditional':
        return (
          <>
            {renderSelect('conditionType', 'Condition Type', [
              { value: 'equals',       label: 'Equals' },
              { value: 'not_equals',   label: 'Not Equals' },
              { value: 'contains',     label: 'Contains' },
              { value: 'not_contains', label: 'Not Contains' },
              { value: 'greater_than', label: 'Greater Than' },
              { value: 'less_than',    label: 'Less Than' },
              { value: 'regex',        label: 'Regex Match' },
              { value: 'is_empty',     label: 'Is Empty' },
            ])}
            {renderInput('conditionValue', 'Condition Value', 'Value to compare against')}
          </>
        );

      case 'transform':
        return (
          <>
            {renderSelect('transformation', 'Transformation', [
              { value: 'passthrough',   label: 'Passthrough' },
              { value: 'uppercase',     label: 'Uppercase' },
              { value: 'lowercase',     label: 'Lowercase' },
              { value: 'trim',          label: 'Trim' },
              { value: 'split',         label: 'Split' },
              { value: 'join',          label: 'Join' },
              { value: 'extract_field', label: 'Extract Field' },
              { value: 'parse_json',    label: 'Parse JSON' },
              { value: 'stringify',     label: 'Stringify' },
            ])}
            {renderInput('field', 'Field Path', 'e.g. data.results[0].name')}
            {renderInput('delimiter', 'Delimiter', 'e.g. , or \\n')}
          </>
        );

      case 'http_request':
        return (
          <>
            {renderSelect('method', 'Method', [
              { value: 'GET',    label: 'GET' },
              { value: 'POST',   label: 'POST' },
              { value: 'PUT',    label: 'PUT' },
              { value: 'PATCH',  label: 'PATCH' },
              { value: 'DELETE', label: 'DELETE' },
            ])}
            {renderInput('url', 'URL', 'https://api.example.com/endpoint')}
            {renderTextarea('headers', 'Headers (JSON)', '{"Authorization": "Bearer …"}', 3)}
            {renderTextarea('body', 'Body', 'Request body…', 4)}
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
        return (
          <p className="text-xs" style={{ color: 'var(--text-disabled)' }}>
            No configurable properties for this node type.
          </p>
        );
    }
  };

  const nodeTypeColor: Record<string, string> = {
    input: 'var(--node-input)',
    agent: 'var(--node-agent)',
    prompt: 'var(--node-prompt)',
    output: 'var(--node-output)',
    conditional: 'var(--node-conditional)',
    transform: 'var(--node-transform)',
    http_request: 'var(--node-http)',
    knowledge: 'var(--node-knowledge)',
  };

  const accentColor = nodeTypeColor[type || ''] || 'var(--accent-mid)';

  return (
    <div
      className="w-72 h-full overflow-y-auto flex flex-col animate-slide-in"
      style={{
        background: 'var(--bg-surface)',
        borderLeft: '1px solid var(--border-subtle)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 shrink-0"
        style={{ borderBottom: '1px solid var(--border-subtle)' }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full"
            style={{ background: accentColor }}
          />
          <div>
            <p className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>Properties</p>
            <p className="text-[9px] uppercase tracking-wider capitalize" style={{ color: accentColor }}>
              {type?.replace('_', ' ')} node
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => { removeNode(selectedNode.id); setSelectedNodeId(null); }}
            title="Delete node"
            className="w-6 h-6 rounded flex items-center justify-center transition-all"
            style={{ color: '#f87171' }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.1)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setSelectedNodeId(null)}
            className="w-6 h-6 rounded flex items-center justify-center transition-all"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Fields */}
      <div className="p-4 space-y-4 flex-1">
        {renderInput('label', 'Label', 'Node label')}
        <div
          className="h-px"
          style={{ background: 'var(--border-subtle)' }}
        />
        {renderFields()}
      </div>
    </div>
  );
};

export default PropertiesPanel;
