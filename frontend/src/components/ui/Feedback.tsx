import { AlertTriangle, Info, Loader2, AlertOctagon, CheckCircle2 } from 'lucide-react'
import { cn } from '../../lib/utils'

/** Summary stat card: muted label (+ optional icon), big mono value, optional sub line. */
export function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
  className,
}: {
  label: string
  value: React.ReactNode
  sub?: string
  icon?: React.ComponentType<{ className?: string }>
  className?: string
}) {
  return (
    <div className={cn('bg-surface border border-line rounded-xl px-4 py-4', className)}>
      <div className="flex items-center justify-between">
        <p className="text-xs text-ink-muted">{label}</p>
        {Icon && <Icon className="w-4 h-4 text-ink-subtle" aria-hidden />}
      </div>
      <p className="mt-1 text-2xl font-mono font-medium text-ink leading-tight">{value}</p>
      {sub && <p className="mt-1 text-xs text-ink-subtle">{sub}</p>}
    </div>
  )
}

type CalloutTone = 'info' | 'warning' | 'danger' | 'success'

const calloutStyles: Record<CalloutTone, { box: string; icon: React.ComponentType<{ className?: string }> }> = {
  info: { box: 'bg-status-info-soft text-status-info border-status-info/30', icon: Info },
  warning: { box: 'bg-status-warning-soft text-status-warning border-status-warning/30', icon: AlertTriangle },
  danger: { box: 'bg-status-error-soft text-status-error border-status-error/30', icon: AlertOctagon },
  success: { box: 'bg-status-success-soft text-status-success border-status-success/30', icon: CheckCircle2 },
}

/** Tinted callout banner (reference: OAuth created dialog). */
export function Callout({
  tone = 'info',
  title,
  children,
  className,
}: {
  tone?: CalloutTone
  title?: string
  children?: React.ReactNode
  className?: string
}) {
  const { box, icon: Icon } = calloutStyles[tone]
  return (
    <div className={cn('flex gap-2.5 rounded-lg border px-3.5 py-3 text-sm', box, className)}>
      <Icon className="w-4 h-4 mt-0.5 shrink-0" aria-hidden />
      <div>
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn('text-[13px] leading-relaxed', title && 'mt-0.5')}>{children}</div>}
      </div>
    </div>
  )
}

/** Centered muted empty state (reference: "No model usage yet"). */
export function EmptyState({
  icon: Icon,
  title,
  description,
  className,
}: {
  icon?: React.ComponentType<{ className?: string }>
  title: string
  description?: string
  className?: string
}) {
  return (
    <div className={cn('text-center py-16', className)}>
      {Icon && <Icon className="w-10 h-10 mx-auto mb-3 text-ink-subtle" aria-hidden />}
      <p className="text-sm font-medium text-ink-muted">{title}</p>
      {description && <p className="mt-1 text-[13px] text-ink-subtle">{description}</p>}
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn('w-5 h-5 animate-spin text-ink-muted', className)} aria-label="Loading" />
}
