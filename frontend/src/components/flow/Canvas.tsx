import React, { useCallback, useRef, useMemo, DragEvent } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
  useReactFlow,
  type NodeTypes,
  type EdgeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import useWorkflowStore from '../../store/workflowStore';

import InputNode from './nodes/InputNode';
import AgentNode from './nodes/AgentNode';
import PromptNode from './nodes/PromptNode';
import OutputNode from './nodes/OutputNode';
import ConditionalNode from './nodes/ConditionalNode';
import TransformNode from './nodes/TransformNode';
import HttpNode from './nodes/HttpNode';
import KnowledgeNode from './nodes/KnowledgeNode';
import CustomEdge from './edges/CustomEdge';

const defaultDataForType: Record<string, Record<string, unknown>> = {
  input:       { label: 'Input', value: '' },
  agent:       { label: 'Agent', provider: 'openai', model: '', temperature: 0.7, maxTokens: 4096, systemPrompt: '' },
  prompt:      { label: 'Prompt', template: '', variables: [] },
  output:      { label: 'Output', format: 'text' },
  conditional: { label: 'Conditional', conditionType: 'equals', conditionValue: '' },
  transform:   { label: 'Transform', transformation: 'passthrough', field: '', delimiter: '' },
  http_request:{ label: 'HTTP Request', method: 'GET', url: '', headers: '', body: '' },
  knowledge:   { label: 'Knowledge Base', knowledgeBaseId: '', topK: 5, threshold: 0.7 },
};

let nodeIdCounter = 0;
const generateId = () => `node_${Date.now()}_${nodeIdCounter++}`;

const Canvas: React.FC = () => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();

  const nodes           = useWorkflowStore((s) => s.nodes);
  const edges           = useWorkflowStore((s) => s.edges);
  const onNodesChange   = useWorkflowStore((s) => s.onNodesChange);
  const onEdgesChange   = useWorkflowStore((s) => s.onEdgesChange);
  const onConnect       = useWorkflowStore((s) => s.onConnect);
  const addNode         = useWorkflowStore((s) => s.addNode);
  const setSelectedNodeId = useWorkflowStore((s) => s.setSelectedNodeId);

  const nodeTypes: NodeTypes = useMemo(() => ({
    input:        InputNode,
    agent:        AgentNode,
    prompt:       PromptNode,
    output:       OutputNode,
    conditional:  ConditionalNode,
    transform:    TransformNode,
    http_request: HttpNode,
    knowledge:    KnowledgeNode,
  }), []);

  const edgeTypes: EdgeTypes = useMemo(() => ({ custom: CustomEdge }), []);

  const onDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const type = event.dataTransfer.getData('application/reactflow');
    if (!type) return;

    const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
    const newNode = {
      id: generateId(),
      type,
      position,
      data: { ...(defaultDataForType[type] || { label: type }) },
    };
    addNode(newNode);
  }, [screenToFlowPosition, addNode]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: { id: string }) => {
    setSelectedNodeId(node.id);
  }, [setSelectedNodeId]);

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, [setSelectedNodeId]);

  const nodeColorMap: Record<string, string> = {
    input:        'var(--node-input)',
    agent:        'var(--node-agent)',
    prompt:       'var(--node-prompt)',
    output:       'var(--node-output)',
    conditional:  'var(--node-conditional)',
    transform:    'var(--node-transform)',
    http_request: 'var(--node-http)',
    knowledge:    'var(--node-knowledge)',
  };

  return (
    <div ref={reactFlowWrapper} className="flex-1 h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={{ type: 'custom', animated: true }}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        fitView
        snapToGrid
        snapGrid={[16, 16]}
        deleteKeyCode={['Backspace', 'Delete']}
        style={{ background: 'var(--bg-base)' }}
      >
        <Controls
          position="bottom-left"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-default)',
            borderRadius: '10px',
            boxShadow: 'var(--shadow-md)',
          }}
        />
        <MiniMap
          position="bottom-right"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-default)',
            borderRadius: '10px',
            boxShadow: 'var(--shadow-md)',
          }}
          maskColor="rgba(10,11,15,0.75)"
          nodeColor={(node) => nodeColorMap[node.type || ''] || 'var(--text-disabled)'}
        />
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1.2}
          color="rgba(255,255,255,0.06)"
        />
      </ReactFlow>
    </div>
  );
};

export default Canvas;
