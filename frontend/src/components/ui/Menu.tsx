import { useEffect, useRef, useState } from 'react'
import { cn } from '../../lib/utils'

/**
 * Minimal dropdown menu: `trigger` renders the clickable element, children
 * render inside the popover panel. Click-outside closes, matching the
 * existing navbar menu behavior.
 */
export default function Menu({
  trigger,
  align = 'right',
  className,
  children,
}: {
  trigger: React.ReactNode
  align?: 'left' | 'right'
  className?: string
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onClickOutside(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [open])

  return (
    <div className="relative" ref={rootRef}>
      <div onClick={() => setOpen((v) => !v)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            'absolute top-full mt-1.5 min-w-36 bg-surface-raised border border-line rounded-xl shadow-menu py-1 z-40 animate-scale-in',
            align === 'right' ? 'right-0' : 'left-0',
            className,
          )}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      )}
    </div>
  )
}

export function MenuItem({
  icon: Icon,
  destructive = false,
  className,
  children,
  ...rest
}: {
  icon?: React.ComponentType<{ className?: string }>
  destructive?: boolean
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        'w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left transition-colors duration-150',
        destructive
          ? 'text-status-error hover:bg-status-error-soft'
          : 'text-ink hover:bg-surface-muted',
        className,
      )}
      {...rest}
    >
      {Icon && <Icon className="w-4 h-4 shrink-0" aria-hidden />}
      {children}
    </button>
  )
}
