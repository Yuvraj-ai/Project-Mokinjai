import type { Node } from '@xyflow/react'

// Index signature added to each interface so they satisfy Record<string, unknown>
// which is required by @xyflow/react's Node<T> constraint.

export interface AgentNodeData {
  label: string
  model: string
  system_prompt: string
  temperature: number
  max_tokens: number
  [key: string]: unknown
}

export interface PromptNodeData {
  label: string
  template: string
  variables: string[]
  [key: string]: unknown
}

export interface OutputNodeData {
  label: string
  format: 'text' | 'json'
  [key: string]: unknown
}

export interface InputNodeData {
  label: string
  input_schema: Record<string, unknown>
  [key: string]: unknown
}

export interface ConditionalNodeData {
  label: string
  condition: string
  operator: 'equals' | 'contains' | 'greater_than' | 'less_than' | 'regex'
  value: string
  [key: string]: unknown
}

export interface TransformNodeData {
  label: string
  transform_type: 'jq' | 'template' | 'script'
  expression: string
  [key: string]: unknown
}

export interface HttpNodeData {
  label: string
  url: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  headers: Record<string, string>
  body: string
  [key: string]: unknown
}

export interface KnowledgeNodeData {
  label: string
  knowledge_base_id: string
  top_k: number
  similarity_threshold: number
  [key: string]: unknown
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
