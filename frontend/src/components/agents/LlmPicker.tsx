import { useMemo, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import type { AgentOption } from '../../api/agents'
import { cn } from '../../lib/utils'

interface LlmPickerProps {
  options: AgentOption[]
  value: string
  onChange: (option: AgentOption | null) => void
}

function labelFor(option: AgentOption): string {
  return `${option.name} · ${option.provider ?? '?'}/${option.model_id ?? '?'}`
}

/**
 * Searchable combobox. The server already ordered the list by
 * `COALESCE(last_used_at, created_at) DESC`, so the first four are the suggestion.
 */
export default function LlmPicker({ options, value, onChange }: LlmPickerProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')

  const selected = options.find((option) => option.id === value) ?? null
  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return options
    return options.filter((option) =>
      `${option.name} ${option.provider ?? ''} ${option.model_id ?? ''}`
        .toLowerCase()
        .includes(needle)
    )
  }, [options, query])

  const suggested = query.trim() ? [] : matches.slice(0, 4)
  const rest = query.trim() ? matches : matches.slice(4)

  const pick = (option: AgentOption) => {
    onChange(option)
    setOpen(false)
    setQuery('')
  }

  const row = (option: AgentOption) => (
    <li key={option.id}>
      <button
        type="button"
        onClick={() => pick(option)}
        className={cn(
          'flex w-full items-center justify-between gap-3 rounded-md px-2 py-1.5 text-left transition-colors duration-150',
          option.id === value ? 'bg-surface-muted' : 'hover:bg-surface-muted',
        )}
      >
        <span className="min-w-0">
          <span className="block truncate text-[13px] text-ink">
            {option.name}
          </span>
          <span className="block truncate font-mono text-[11px] text-ink-subtle">
            {option.provider}/{option.model_id}
          </span>
        </span>
        <span
          className={cn(
            'shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide',
            option.status === 'verified'
              ? 'bg-status-success-soft text-status-success'
              : 'bg-status-warning-soft text-status-warning',
          )}
        >
          {option.status ?? 'ready'}
        </span>
      </button>
    </li>
  )

  return (
    <div className="relative">
      <span className="mb-1.5 block text-[13px] font-medium text-ink">
        LLM
      </span>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-left transition-colors duration-150 hover:border-line-strong focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <span className={cn('truncate text-sm', selected ? 'text-ink' : 'text-ink-subtle')}>
          {selected ? labelFor(selected) : 'Choose a verified model'}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-ink-subtle" />
      </button>

      {open && (
        <div className="absolute left-0 right-0 z-30 mt-1.5 rounded-xl border border-line bg-surface-raised p-1.5 shadow-menu">
          <div className="mb-1 flex items-center gap-2 rounded-md border border-line px-2 py-1.5">
            <Search className="h-3.5 w-3.5 text-ink-subtle" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search models…"
              className="w-full bg-transparent text-[13px] text-ink placeholder:text-ink-subtle focus:outline-none"
            />
          </div>
          <ul className="max-h-64 overflow-y-auto">
            {suggested.length > 0 && (
              <li className="px-2 pt-1.5 font-mono text-[10px] uppercase tracking-wider text-ink-subtle">
                Suggested
              </li>
            )}
            {suggested.map(row)}
            {rest.length > 0 && (
              <li className="px-2 pt-1.5 font-mono text-[10px] uppercase tracking-wider text-ink-subtle">
                All
              </li>
            )}
            {rest.map(row)}
            {matches.length === 0 && (
              <li className="px-2 py-2 text-xs text-ink-subtle">
                No verified model matches that search.
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  )
}
