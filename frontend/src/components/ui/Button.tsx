import { forwardRef } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive'
type ButtonSize = 'sm' | 'md'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-primary text-primary-fg hover:bg-primary-hover disabled:bg-ink-subtle disabled:text-canvas',
  secondary:
    'bg-surface text-ink border border-line hover:border-line-strong disabled:opacity-50',
  ghost: 'text-ink-muted hover:text-ink hover:bg-surface-muted disabled:opacity-50',
  destructive:
    'bg-surface text-status-error border border-status-error/40 hover:bg-status-error-soft disabled:opacity-50',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-[13px] gap-1.5 rounded-lg',
  md: 'h-9 px-4 text-sm gap-2 rounded-lg',
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading = false, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center font-medium whitespace-nowrap transition-colors duration-150',
        'focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
        sizeClasses[size],
        variantClasses[variant],
        className,
      )}
      {...rest}
    >
      {loading && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
})

export default Button
