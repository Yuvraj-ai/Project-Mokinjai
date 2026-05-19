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
  input: { label: 'Input', value: '' },
  agent: { label: 'Agent', provider: 'openai', model: '', temperature: 0.7, maxTokens: 4096, systemPrompt: '' },
  prompt: { label: 'Prompt', template: '', variables: [] },
  output: { label: 'Output', format: 'text' },
  conditional: { label: 'Conditional', conditionType: 'equals', conditionValue: '' },
  transform: { label: 'Transform', transformation: 'passthrough', field: '', delimiter: '' },
  http_request: { label: 'HTTP Request', method: 'GET', url: '', headers: '', body: '' },
  knowledge: { label: 'Knowledge Base', knowledgeBaseId: '', topK: 5, threshold: 0.7 },
};

let nodeIdCounter = 0;
const generateId = () => `node_${Date.now()}_${nodeIdCounter++}`;

const Canvas: React.FC = () => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();

  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const onNodesChange = useWorkflowStore((s) => s.onNodesChange);
  const onEdgesChange = useWorkflowStore((s) => s.onEdgesChange);
  const onConnect = useWorkflowStore((s) => s.onConnect);
  const addNode = useWorkflowStore((s) => s.addNode);
  const setSelectedNodeId = useWorkflowStore((s) => s.setSelectedNodeId);

  const nodeTypes: NodeTypes = useMemo(
    () => ({
      input: InputNode,
      agent: AgentNode,
      prompt: PromptNode,
      output: OutputNode,
      conditional: ConditionalNode,
      transform: TransformNode,
      http_request: HttpNode,
      knowledge: KnowledgeNode,
    }),
    []
  );

  const edgeTypes: EdgeTypes = useMemo(
    () => ({
      custom: CustomEdge,
    }),
    []
  );

  const onDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/reactflow');
      if (!type) return;

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const newNode = {
        id: generateId(),
        type,
        position,
        data: { ...(defaultDataForType[type] || { label: type }) },
      };

      addNode(newNode);
    },
    [screenToFlowPosition, addNode]
  );

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: { id: string }) => {
      setSelectedNodeId(node.id);
    },
    [setSelectedNodeId]
  );

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, [setSelectedNodeId]);

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
        className="bg-gray-50"
      >
        <Controls position="bottom-left" className="!shadow-md !border !border-gray-200 !rounded-lg" />
        <MiniMap
          position="bottom-right"
          className="!shadow-md !border !border-gray-200 !rounded-lg"
          maskColor="rgba(0, 0, 0, 0.1)"
          nodeColor={(node) => {
            const colorMap: Record<string, string> = {
              input: '#22c55e',
              agent: '#8b5cf6',
              prompt: '#3b82f6',
              output: '#ef4444',
              conditional: '#f59e0b',
              transform: '#06b6d4',
              http_request: '#ec4899',
              knowledge: '#14b8a6',
            };
            return colorMap[node.type || ''] || '#94a3b8';
          }}
        />
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#d1d5db" />
      </ReactFlow>
    </div>
  );
};

export default Canvas;
