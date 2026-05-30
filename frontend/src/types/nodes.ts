import type { Node } from '@xyflow/react'

export interface AgentNodeData {
  [key: string]: unknown
  label: string
  model: string
  system_prompt: string
  temperature: number
  max_tokens: number
}

export interface PromptNodeData {
  [key: string]: unknown
  label: string
  template: string
  variables: string[]
}

export interface OutputNodeData {
  [key: string]: unknown
  label: string
  format: 'text' | 'json'
}

export interface InputNodeData {
  [key: string]: unknown
  label: string
  input_schema: Record<string, unknown>
}

export interface ConditionalNodeData {
  [key: string]: unknown
  label: string
  condition: string
  operator: 'equals' | 'contains' | 'greater_than' | 'less_than' | 'regex'
  value: string
}

export interface TransformNodeData {
  [key: string]: unknown
  label: string
  transform_type: 'jq' | 'template' | 'script'
  expression: string
}

export interface HttpNodeData {
  [key: string]: unknown
  label: string
  url: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  headers: Record<string, string>
  body: string
}

export interface KnowledgeNodeData {
  [key: string]: unknown
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
