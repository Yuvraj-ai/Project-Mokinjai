import { useState } from 'react'
import {
  Bot,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Database,
  FolderOpen,
  Globe,
  Plug,
  Terminal,
  Wrench,
} from 'lucide-react'
import type { ActivityEvent } from '../../api/playground'

const KIND_META: Record<
  string,
  { icon: typeof Wrench; label: (event: ActivityEvent) => string }
> = {
  sql: { icon: Database, label: (e) => `Queried ${name(e)}` },
  code: { icon: Terminal, label: () => 'Ran Python in the sandbox' },
  skill: { icon: BookOpen, label: (e) => `Read skill ${name(e)}` },
  mcp: { icon: Plug, label: (e) => `Connector call ${name(e)}` },
  web: { icon: Globe, label: () => 'Searched the web' },
  subagent: { icon: Bot, label: (e) => `Called ${name(e)}` },
  tool: { icon: Wrench, label: (e) => `Called ${name(e)}` },
}

function name(event: ActivityEvent): string {
  return event.name ?? ''
}

function filesLabel(event: ActivityEvent): string {
  const names = event.names ?? []
  if (names.length === 0) return 'Staged files'
  const shown = names.slice(0, 3).join(', ')
  return `Staged ${names.length > 3 ? `${shown} +${names.length - 3}` : shown}`
}

const START_FORM: Record<string, string> = {
  Called: 'Calling',
  Queried: 'Querying',
  Ran: 'Running',
  Read: 'Reading',
  Searched: 'Searching',
  Staged: 'Staging',
}

function describe(event: ActivityEvent): string {
  if (event.type === 'files_staged') return filesLabel(event)
  const meta = KIND_META[event.kind ?? 'tool'] ?? KIND_META.tool
  const label = meta.label(event)
  if (event.type === 'tool_end') return label
  // tool_start: same label, in-progress verb ("Called get_time" → "Calling get_time").
  return label.replace(/^\w+/, (verb) => START_FORM[verb] ?? verb)
}

function bodyOf(event: ActivityEvent): string | null {
  const pick = (value: unknown): string | null => {
    if (value === null || value === undefined) return null
    if (typeof value === 'string') return value
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }
  if (event.error) return String(event.error)
  if (event.type === 'files_staged') return pick(event.names)
  return pick(event.type === 'tool_start' ? event.args : event.result)
}

/**
 * One collapsible activity card (spec P3). Live tool_start rows show a
 * spinner feel via the "Calling —" label; tool_end swaps in the result and
 * duration. Replays render the persisted events through this same component.
 */
export default function ActivityCard({ event }: { event: ActivityEvent }) {
  const [open, setOpen] = useState(false)
  const isFiles = event.type === 'files_staged'
  const Icon = isFiles ? FolderOpen : (KIND_META[event.kind ?? 'tool'] ?? KIND_META.tool).icon
  const body = bodyOf(event)

  return (
    <div className="mb-1.5 rounded-lg border border-line bg-surface-muted">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-[11.5px] text-ink-muted"
      >
        {open ? (
          <ChevronDown className="h-3 w-3 shrink-0" aria-hidden />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0" aria-hidden />
        )}
        <Icon className={`h-3 w-3 shrink-0 ${event.error ? 'text-status-error' : ''}`} aria-hidden />
        <span className="min-w-0 flex-1 truncate font-mono">{describe(event)}</span>
        {event.duration_ms != null && (
          <span className="shrink-0 tabular-nums">{(event.duration_ms / 1000).toFixed(1)}s</span>
        )}
      </button>
      {open && body && (
        <pre className="max-h-56 overflow-auto whitespace-pre-wrap border-t border-line px-3 py-2 font-mono text-[11px] text-ink-muted">
          {body}
        </pre>
      )}
    </div>
  )
}
