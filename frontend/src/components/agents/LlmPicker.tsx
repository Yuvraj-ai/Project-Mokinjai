import { useMemo, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import type { AgentOption } from '../../api/agents'

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
        className={`flex w-full items-center justify-between gap-3 rounded-md px-2 py-1.5 text-left ${
          option.id === value
            ? 'bg-ink-800/5 dark:bg-ink-600/50'
            : 'hover:bg-ink-50 dark:hover:bg-ink-700'
        }`}
      >
        <span className="min-w-0">
          <span className="block truncate text-xs text-ink-700 dark:text-cream-100">
            {option.name}
          </span>
          <span className="block truncate font-mono text-[10px] text-ink-400">
            {option.provider}/{option.model_id}
          </span>
        </span>
        <span
          className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] uppercase tracking-wider ${
            option.status === 'verified'
              ? 'bg-status-success/10 text-status-success'
              : 'bg-status-warning/10 text-status-warning'
          }`}
        >
          {option.status ?? 'ready'}
        </span>
      </button>
    </li>
  )

  return (
    <div className="relative">
      <span className="mb-1 block text-[10px] uppercase tracking-wider font-semibold text-ink-400">
        LLM
      </span>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between gap-2 rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-left"
      >
        <span className={`truncate text-xs ${selected ? 'text-ink-800 dark:text-cream-100' : 'text-ink-300'}`}>
          {selected ? labelFor(selected) : 'Choose a verified model'}
        </span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-ink-300" />
      </button>

      {open && (
        <div className="absolute left-0 right-0 z-30 mt-1 rounded-lg border border-ink-100 dark:border-ink-600 bg-white dark:bg-ink-800 p-1.5 shadow-lg">
          <div className="mb-1 flex items-center gap-2 rounded-md border border-ink-100 dark:border-ink-600 px-2 py-1">
            <Search className="h-3 w-3 text-ink-300" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search models…"
              className="w-full bg-transparent text-xs text-ink-700 dark:text-cream-100 placeholder:text-ink-300"
            />
          </div>
          <ul className="max-h-64 overflow-y-auto">
            {suggested.length > 0 && (
              <li className="px-2 pt-1 text-[9px] uppercase tracking-wider text-ink-300">
                Suggested
              </li>
            )}
            {suggested.map(row)}
            {rest.length > 0 && (
              <li className="px-2 pt-1 text-[9px] uppercase tracking-wider text-ink-300">
                All
              </li>
            )}
            {rest.map(row)}
            {matches.length === 0 && (
              <li className="px-2 py-2 text-[11px] text-ink-400">
                No verified model matches that search.
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  )
}
