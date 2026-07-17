import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  function Input(
    { className, label, error, leftIcon, rightIcon, id, ...props },
    ref,
  ) {
    const inputId = id ?? props.name
    return (
      <div className="w-full">
        {label ? (
          <label
            htmlFor={inputId}
            className="mb-1.5 block text-sm font-medium text-slate-700"
          >
            {label}
          </label>
        ) : null}
        <div className="relative">
          {leftIcon ? (
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-muted">
              {leftIcon}
            </span>
          ) : null}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              'h-11 w-full rounded-lg border border-border bg-white px-3 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-brand focus:ring-2 focus:ring-brand/20',
              leftIcon && 'pl-10',
              rightIcon && 'pr-10',
              error && 'border-danger focus:border-danger focus:ring-danger/20',
              className,
            )}
            {...props}
          />
          {rightIcon ? (
            <span className="absolute inset-y-0 right-3 flex items-center text-muted [&_button]:pointer-events-auto">
              {rightIcon}
            </span>
          ) : null}
        </div>
        {error ? <p className="mt-1 text-xs text-danger">{error}</p> : null}
      </div>
    )
  },
)
