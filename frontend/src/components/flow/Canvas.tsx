import React, { useCallback, useRef, useMemo, useEffect, DragEvent } from 'react';
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
  const removeNode = useWorkflowStore((s) => s.removeNode);
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedNodeId) {
        const tag = (e.target as HTMLElement).tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
        e.preventDefault();
        removeNode(selectedNodeId);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectedNodeId, removeNode]);

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
        className="bg-cream-50 dark:bg-ink-900"
      >
        <Controls
          position="bottom-left"
          showInteractive={false}
          className="!shadow-sm !border !border-ink-200/40 !rounded-lg !bg-white/90 dark:!bg-ink-800/90 !backdrop-blur-sm [&>button]:!bg-transparent [&>button]:!border-b [&>button]:!border-ink-200/30 dark:[&>button]:!border-ink-700/50 [&>button]:!text-ink-500 dark:[&>button]:!text-ink-300 [&>button:hover]:!bg-ink-100/50 dark:[&>button:hover]:!bg-ink-700/50 [&>button]:!w-8 [&>button]:!h-8 [&>button]:!flex [&>button]:!items-center [&>button]:!justify-center [&>button:last-child]:!border-b-0"
        />
        <MiniMap
          position="bottom-right"
          className="!shadow-sm !border !border-ink-200/40 !rounded-lg !bg-white/90 dark:!bg-ink-800/90 !backdrop-blur-sm"
          maskColor="rgba(15, 15, 20, 0.15)"
          nodeColor={(node) => {
            const colorMap: Record<string, string> = {
              input: '#2D6A4F',
              agent: '#7B2D8B',
              prompt: '#264653',
              output: '#9B2226',
              conditional: '#BC6C25',
              transform: '#0E7C86',
              http_request: '#8B2252',
              knowledge: '#1A756F',
            };
            return colorMap[node.type || ''] || '#B8A99A';
          }}
          nodeStrokeWidth={2}
          pannable
          zoomable
        />
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#EDE9E0" className="dark:opacity-30" />
      </ReactFlow>
    </div>
  );
};

export default Canvas;
