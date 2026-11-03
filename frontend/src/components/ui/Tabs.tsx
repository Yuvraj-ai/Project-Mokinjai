import { cn } from '../../lib/utils'

/** Underline tabs (reference: model library). */
export function Tabs({
  tabs,
  active,
  onChange,
  className,
}: {
  tabs: { id: string; label: string; count?: number }[]
  active: string
  onChange: (id: string) => void
  className?: string
}) {
  return (
    <div className={cn('flex items-center gap-6 border-b border-line', className)}>
      {tabs.map((tab) => {
        const isActive = tab.id === active
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            aria-current={isActive ? 'page' : undefined}
            className={cn(
              'pb-2 -mb-px text-sm border-b-2 transition-colors duration-150',
              isActive
                ? 'text-ink border-ink font-medium'
                : 'text-ink-muted border-transparent hover:text-ink',
            )}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="ml-1.5 text-ink-subtle font-mono text-xs">{tab.count}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}

/** Pill-in-track segmented control (reference: API-calls time range). */
export function SegmentedControl({
  options,
  value,
  onChange,
  className,
}: {
  options: { id: string; label: string }[]
  value: string
  onChange: (id: string) => void
  className?: string
}) {
  return (
    <div className={cn('inline-flex items-center bg-surface-muted rounded-lg p-0.5', className)}>
      {options.map((option) => {
        const isActive = option.id === value
        return (
          <button
            key={option.id}
            onClick={() => onChange(option.id)}
            aria-pressed={isActive}
            className={cn(
              'h-7 px-2.5 rounded-md text-[13px] font-medium transition-colors duration-150',
              isActive
                ? 'bg-surface border border-line text-ink'
                : 'text-ink-muted hover:text-ink border border-transparent',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
