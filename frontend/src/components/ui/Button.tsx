import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'danger' | 'outline'
  size?: 'sm' | 'md' | 'lg'
}

export function Button({ className, variant = 'primary', size = 'md', ...props }: Props) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none',
        size === 'sm' && 'h-8 px-3 text-xs',
        size === 'md' && 'h-9 px-4 text-sm',
        size === 'lg' && 'h-11 px-5 text-base',
        variant === 'primary' && 'bg-accent text-surface hover:brightness-110 shadow-[0_0_20px_rgba(61,214,198,0.25)]',
        variant === 'ghost' && 'bg-transparent text-muted hover:text-ink hover:bg-surface-3',
        variant === 'danger' && 'bg-danger/90 text-white hover:bg-danger',
        variant === 'outline' && 'border border-border-bright bg-surface-2 text-ink hover:border-accent/50',
        className,
      )}
      {...props}
    />
  )
}
