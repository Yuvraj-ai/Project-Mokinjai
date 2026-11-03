import { Check } from 'lucide-react'
import { cn } from '../../lib/utils'

export function Switch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  disabled?: boolean
  label?: string
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative w-9 h-5 rounded-full border transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
        checked ? 'bg-primary border-primary' : 'bg-surface-muted border-line',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      <span
        className={cn(
          'absolute top-0.5 left-0.5 w-3.5 h-3.5 rounded-full transition-transform duration-150',
          checked ? 'translate-x-4 bg-primary-fg' : 'translate-x-0 bg-ink-subtle',
        )}
      />
    </button>
  )
}

export function Checkbox({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  disabled?: boolean
  label?: string
}) {
  return (
    <button
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'w-4 h-4 rounded border flex items-center justify-center transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
        checked ? 'bg-primary border-primary text-primary-fg' : 'bg-surface border-line-strong',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      {checked && <Check className="w-3 h-3" strokeWidth={3} aria-hidden />}
    </button>
  )
}

export function Radio({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean
  onChange: () => void
  disabled?: boolean
  label?: string
}) {
  return (
    <button
      role="radio"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onChange}
      className={cn(
        'w-4 h-4 rounded-full border flex items-center justify-center transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
        checked ? 'border-primary' : 'border-line-strong',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      {checked && <span className="w-2 h-2 rounded-full bg-primary" />}
    </button>
  )
}
