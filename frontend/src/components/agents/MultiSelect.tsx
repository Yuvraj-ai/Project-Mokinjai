import { useMemo, useState } from 'react'
import { Check, Search } from 'lucide-react'
import type { AgentOption } from '../../api/agents'

interface MultiSelectProps {
  label: string
  options: AgentOption[]
  values: string[]
  onChange: (ids: string[]) => void
  hint?: (option: AgentOption) => string | undefined
  disabled?: (option: AgentOption) => boolean
  emptyText?: string
  error?: string
}

/** A searchable checkbox list. Selection order follows the user's clicks. */
export default function MultiSelect({
  label,
  options,
  values,
  onChange,
  hint,
  disabled,
  emptyText = 'Nothing available yet.',
  error,
}: MultiSelectProps) {
  const [query, setQuery] = useState('')
  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return options
    return options.filter((option) =>
      `${option.name} ${option.description ?? ''}`.toLowerCase().includes(needle)
    )
  }, [options, query])

  const toggle = (id: string) => {
    onChange(values.includes(id) ? values.filter((value) => value !== id) : [...values, id])
  }

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-400">
          {label}
        </span>
        <span className="text-[10px] text-ink-400">{values.length} selected</span>
      </div>

      <div className="rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50">
        <div className="flex items-center gap-2 border-b border-ink-100/70 dark:border-ink-600/70 px-2 py-1.5">
          <Search className="h-3 w-3 text-ink-300" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${label.toLowerCase()}…`}
            className="w-full bg-transparent text-xs text-ink-700 dark:text-cream-100 placeholder:text-ink-300"
          />
        </div>

        <ul className="max-h-40 overflow-y-auto p-1">
          {matches.map((option) => {
            const selected = values.includes(option.id)
            const blocked = disabled?.(option) ?? false
            return (
              <li key={option.id}>
                <button
                  type="button"
                  disabled={blocked}
                  onClick={() => toggle(option.id)}
                  className={`flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left ${
                    blocked
                      ? 'opacity-40'
                      : selected
                        ? 'bg-ink-800/5 dark:bg-ink-600/50'
                        : 'hover:bg-ink-50 dark:hover:bg-ink-700'
                  }`}
                >
                  <span
                    className={`mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border ${
                      selected
                        ? 'border-accent-warm bg-accent-warm text-white'
                        : 'border-ink-200 dark:border-ink-500'
                    }`}
                  >
                    {selected && <Check className="h-2.5 w-2.5" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-xs text-ink-700 dark:text-cream-100">
                      {option.name}
                    </span>
                    {(option.description || hint?.(option)) && (
                      <span className="block truncate text-[10px] text-ink-400">
                        {hint?.(option) ?? option.description}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            )
          })}
          {matches.length === 0 && (
            <li className="px-2 py-2 text-[11px] text-ink-400">{emptyText}</li>
          )}
        </ul>
      </div>

      {error && <p className="mt-1 text-[11px] text-status-error">{error}</p>}
    </div>
  )
}
