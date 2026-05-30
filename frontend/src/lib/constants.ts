export const API_BASE_URL = import.meta.env.VITE_API_URL || ''

export const MODULE_TYPES = [
  {
    type: 'input',
    label: 'Input',
    description: 'Workflow start input',
    category: 'Core',
    color: '#2D6A4F',
  },
  {
    type: 'agent',
    label: 'AI Agent',
    description: 'LLM-powered agent',
    category: 'AI',
    color: '#7B2D8B',
  },
  {
    type: 'prompt',
    label: 'Prompt Template',
    description: 'Format prompts with variables',
    category: 'AI',
    color: '#264653',
  },
  {
    type: 'output',
    label: 'Output',
    description: 'Final workflow output',
    category: 'Core',
    color: '#9B2226',
  },
  {
    type: 'conditional',
    label: 'Conditional',
    description: 'Branch based on conditions',
    category: 'Logic',
    color: '#BC6C25',
  },
  {
    type: 'transform',
    label: 'Transform',
    description: 'Transform data formats',
    category: 'Logic',
    color: '#0E7C86',
  },
  {
    type: 'http_request',
    label: 'HTTP Request',
    description: 'Make external API calls',
    category: 'Integration',
    color: '#8B2252',
  },
  {
    type: 'knowledge',
    label: 'Knowledge Base',
    description: 'Search knowledge base',
    category: 'AI',
    color: '#1A756F',
  },
] as const

export type ModuleType = typeof MODULE_TYPES[number]['type']
