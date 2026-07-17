import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

const variants: Record<Variant, string> = {
  primary:
    'bg-brand text-white hover:bg-brand-dark shadow-sm hover:shadow-md active:scale-[0.98]',
  secondary:
    'bg-white text-slate-700 border border-border hover:bg-slate-50 shadow-sm',
  ghost: 'bg-transparent text-slate-600 hover:bg-slate-100',
  danger: 'bg-danger text-white hover:bg-red-600 shadow-sm',
  outline:
    'bg-transparent text-brand border border-brand/30 hover:bg-brand-soft',
}

const sizes: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5 rounded-lg',
  md: 'h-10 px-4 text-sm gap-2 rounded-lg',
  lg: 'h-12 px-5 text-sm gap-2 rounded-xl',
}

export function Button({
  className,
  variant = 'primary',
  size = 'md',
  leftIcon,
  rightIcon,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center font-medium transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {leftIcon}
      {children}
      {rightIcon}
    </button>
  )
}
