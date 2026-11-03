import { forwardRef } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '../../lib/utils'

export function Label({ children, htmlFor, required }: { children: React.ReactNode; htmlFor?: string; required?: boolean }) {
  return (
    <label htmlFor={htmlFor} className="block text-[13px] font-medium text-ink mb-1.5">
      {children}
      {required && <span className="text-status-error ml-0.5">*</span>}
    </label>
  )
}

export function HelperText({ children, error }: { children?: React.ReactNode; error?: boolean }) {
  if (!children) return null
  return (
    <p className={cn('mt-1.5 text-xs', error ? 'text-status-error' : 'text-ink-subtle')}>{children}</p>
  )
}

const controlBase =
  'w-full rounded-lg border border-line bg-surface text-sm text-ink placeholder:text-ink-subtle ' +
  'transition-colors duration-150 focus:border-line-strong focus:ring-2 focus:ring-ring disabled:opacity-50'

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return <input ref={ref} className={cn(controlBase, 'h-9 px-3', className)} {...rest} />
  },
)

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return <textarea ref={ref} className={cn(controlBase, 'px-3 py-2 min-h-20 resize-y', className)} {...rest} />
  },
)

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <div className="relative">
        <select
          ref={ref}
          className={cn(controlBase, 'h-9 pl-3 pr-8 appearance-none cursor-pointer', className)}
          {...rest}
        >
          {children}
        </select>
        <ChevronDown
          aria-hidden
          className="w-4 h-4 text-ink-subtle pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2"
        />
      </div>
    )
  },
)
