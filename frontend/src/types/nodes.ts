import type { Node } from '@xyflow/react'

export interface AgentNodeData {
  label: string
  model: string
  system_prompt: string
  temperature: number
  max_tokens: number
}

export interface PromptNodeData {
  label: string
  template: string
  variables: string[]
}

export interface OutputNodeData {
  label: string
  format: 'text' | 'json'
}

export interface InputNodeData {
  label: string
  input_schema: Record<string, unknown>
}

export interface ConditionalNodeData {
  label: string
  condition: string
  operator: 'equals' | 'contains' | 'greater_than' | 'less_than' | 'regex'
  value: string
}

export interface TransformNodeData {
  label: string
  transform_type: 'jq' | 'template' | 'script'
  expression: string
}

export interface HttpNodeData {
  label: string
  url: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  headers: Record<string, string>
  body: string
}

export interface KnowledgeNodeData {
  label: string
  knowledge_base_id: string
  top_k: number
  similarity_threshold: number
}

export type AppNode =
  | Node<AgentNodeData, 'agent'>
  | Node<PromptNodeData, 'prompt'>
  | Node<OutputNodeData, 'output'>
  | Node<InputNodeData, 'input'>
  | Node<ConditionalNodeData, 'conditional'>
  | Node<TransformNodeData, 'transform'>
  | Node<HttpNodeData, 'http_request'>
  | Node<KnowledgeNodeData, 'knowledge'>
