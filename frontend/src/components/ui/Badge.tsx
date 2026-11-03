import { cn } from '../../lib/utils'

type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info'

export type BadgeTone = Tone

const toneText: Record<Tone, string> = {
  neutral: 'text-ink-muted',
  success: 'text-status-success',
  warning: 'text-status-warning',
  danger: 'text-status-error',
  info: 'text-status-info',
}

const toneSoft: Record<Tone, string> = {
  neutral: 'bg-surface-muted',
  success: 'bg-status-success-soft',
  warning: 'bg-status-warning-soft',
  danger: 'bg-status-error-soft',
  info: 'bg-status-info-soft',
}

const toneDot: Record<Tone, string> = {
  neutral: 'bg-ink-subtle',
  success: 'bg-status-success',
  warning: 'bg-status-warning',
  danger: 'bg-status-error',
  info: 'bg-status-info',
}

/**
 * tone="outline": mono micro-badge for operation kinds ("ADD", "Reg").
 * Otherwise: soft tinted pill; `dot` renders the little status dot first.
 */
export default function Badge({
  tone = 'neutral',
  variant = 'soft',
  dot = false,
  className,
  children,
}: {
  tone?: Tone
  variant?: 'soft' | 'outline'
  dot?: boolean
  className?: string
  children: React.ReactNode
}) {
  if (variant === 'outline') {
    return (
      <span
        className={cn(
          'inline-flex items-center rounded-full border border-line px-2 py-0.5',
          'text-[10px] font-mono uppercase tracking-wide',
          tone === 'neutral' ? 'text-ink-muted' : toneText[tone],
          className,
        )}
      >
        {children}
      </span>
    )
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium',
        toneSoft[tone],
        toneText[tone],
        className,
      )}
    >
      {dot && <span className={cn('w-1.5 h-1.5 rounded-full', toneDot[tone])} aria-hidden />}
      {children}
    </span>
  )
}
