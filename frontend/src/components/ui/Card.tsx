import { cn } from '../../lib/utils'

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={cn('bg-surface border border-line rounded-xl', className)}>{children}</div>
  )
}

export function CardTitle({ count, children }: { count?: number | string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-5 pt-4 pb-3">
      <h2 className="text-[15px] font-semibold text-ink">{children}</h2>
      {count !== undefined && (
        <span className="min-w-6 h-6 px-1.5 inline-flex items-center justify-center rounded-full border border-line text-xs font-mono text-ink-muted">
          {count}
        </span>
      )}
    </div>
  )
}

export function CardBody({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn('px-5 pb-5', className)}>{children}</div>
}
