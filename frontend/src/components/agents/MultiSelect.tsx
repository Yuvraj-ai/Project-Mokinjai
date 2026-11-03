import { useMemo, useState } from 'react'
import { Check, Search } from 'lucide-react'
import type { AgentOption } from '../../api/agents'
import { Checkbox } from '../ui/Controls'
import { cn } from '../../lib/utils'

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
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-[13px] font-medium text-ink">{label}</span>
        <span className="font-mono text-xs text-ink-subtle">{values.length} selected</span>
      </div>

      <div className="rounded-lg border border-line bg-surface">
        <div className="flex items-center gap-2 border-b border-line px-3 py-2">
          <Search className="h-3.5 w-3.5 text-ink-subtle" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${label.toLowerCase()}…`}
            className="w-full bg-transparent text-[13px] text-ink placeholder:text-ink-subtle focus:outline-none"
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
                  className={cn(
                    'flex w-full items-start gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors duration-150',
                    blocked ? 'opacity-40' : selected ? 'bg-surface-muted' : 'hover:bg-surface-muted',
                  )}
                >
                  <span className="mt-0.5 shrink-0">
                    <Checkbox checked={selected} onChange={() => toggle(option.id)} disabled={blocked} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] text-ink">
                      {option.name}
                    </span>
                    {(option.description || hint?.(option)) && (
                      <span className="block truncate text-xs text-ink-subtle">
                        {hint?.(option) ?? option.description}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            )
          })}
          {matches.length === 0 && (
            <li className="px-2 py-2 text-xs text-ink-subtle">{emptyText}</li>
          )}
        </ul>
      </div>

      {error && <p className="mt-1.5 text-xs text-status-error">{error}</p>}
    </div>
  )
}
