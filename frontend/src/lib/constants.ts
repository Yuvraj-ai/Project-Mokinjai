export const API_BASE_URL = import.meta.env.VITE_API_URL || ''

export const MODULE_TYPES = [
  {
    type: 'input',
    label: 'Input',
    description: 'Workflow start input',
    category: 'Core',
    color: '#22c55e',
  },
  {
    type: 'agent',
    label: 'AI Agent',
    description: 'LLM-powered agent',
    category: 'AI',
    color: '#8b5cf6',
  },
  {
    type: 'prompt',
    label: 'Prompt Template',
    description: 'Format prompts with variables',
    category: 'AI',
    color: '#3b82f6',
  },
  {
    type: 'output',
    label: 'Output',
    description: 'Final workflow output',
    category: 'Core',
    color: '#ef4444',
  },
  {
    type: 'conditional',
    label: 'Conditional',
    description: 'Branch based on conditions',
    category: 'Logic',
    color: '#f59e0b',
  },
  {
    type: 'transform',
    label: 'Transform',
    description: 'Transform data formats',
    category: 'Logic',
    color: '#06b6d4',
  },
  {
    type: 'http_request',
    label: 'HTTP Request',
    description: 'Make external API calls',
    category: 'Integration',
    color: '#ec4899',
  },
  {
    type: 'knowledge',
    label: 'Knowledge Base',
    description: 'Search knowledge base',
    category: 'AI',
    color: '#14b8a6',
  },
] as const

export type ModuleType = typeof MODULE_TYPES[number]['type']
