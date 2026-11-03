import { useEffect } from 'react'
import { X } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface ModalProps {
  open: boolean
  onClose?: () => void
  title: string
  description?: string
  /** Right-aligned footer content (usually secondary + primary buttons). */
  footer?: React.ReactNode
  width?: 'sm' | 'md' | 'lg'
  children: React.ReactNode
}

const widths = { sm: 'max-w-sm', md: 'max-w-lg', lg: 'max-w-2xl' }

export default function Modal({ open, onClose, title, description, footer, width = 'md', children }: ModalProps) {
  useEffect(() => {
    if (!open || !onClose) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/40 dark:bg-black/60"
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          'relative bg-surface border border-line rounded-2xl shadow-drawer w-full animate-scale-in',
          'max-h-[85vh] flex flex-col',
          widths[width],
        )}
      >
        <div className="flex items-start justify-between px-6 pt-5 pb-1">
          <div>
            <h2 className="text-base font-semibold text-ink">{title}</h2>
            {description && <p className="mt-1 text-sm text-ink-muted">{description}</p>}
          </div>
          {onClose && (
            <button
              onClick={onClose}
              aria-label="Close"
              className="p-1 rounded-md text-ink-subtle hover:text-ink hover:bg-surface-muted transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="px-6 py-4 overflow-y-auto">{children}</div>
        {footer && (
          <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-line">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
