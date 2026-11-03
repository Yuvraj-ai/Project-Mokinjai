import { cn } from '../../lib/utils'

/**
 * Table kit: card-framed table with the muted header strip, hairline row
 * dividers, and a footer strip for rows-per-page / total / pagination.
 * Numeric cells pass `numeric` for right-aligned mono text.
 */
export function TableFrame({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={cn('bg-surface border border-line rounded-xl overflow-hidden', className)}>
      {children}
    </div>
  )
}

export function Table({ className, children }: { className?: string; children: React.ReactNode }) {
  return <table className={cn('w-full text-sm', className)}>{children}</table>
}

export function Th({
  numeric = false,
  className,
  children,
}: {
  numeric?: boolean
  className?: string
  children?: React.ReactNode
}) {
  return (
    <th
      scope="col"
      className={cn(
        'bg-surface-muted px-4 py-2.5 text-[13px] font-medium text-ink-muted whitespace-nowrap',
        numeric ? 'text-right' : 'text-left',
        className,
      )}
    >
      {children}
    </th>
  )
}

export function Td({
  numeric = false,
  mono = false,
  className,
  children,
}: {
  numeric?: boolean
  mono?: boolean
  className?: string
  children?: React.ReactNode
}) {
  return (
    <td
      className={cn(
        'px-4 py-3 border-t border-line text-ink',
        numeric && 'text-right font-mono',
        mono && 'font-mono text-[13px]',
        className,
      )}
    >
      {children}
    </td>
  )
}

export function Tr({
  className,
  onClick,
  children,
}: {
  className?: string
  onClick?: () => void
  children: React.ReactNode
}) {
  return (
    <tr
      onClick={onClick}
      className={cn('transition-colors duration-150', onClick && 'cursor-pointer hover:bg-surface-muted', className)}
    >
      {children}
    </tr>
  )
}

export function TableFooter({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 px-4 py-2.5 border-t border-line text-[13px] text-ink-muted',
        className,
      )}
    >
      {children}
    </div>
  )
}
