import type { ReactNode } from 'react'

export interface CardProps {
  title?: string
  subtitle?: string
  right?: ReactNode
  children: ReactNode
  className?: string
}

export function Card({ title, subtitle, right, children, className = '' }: CardProps) {
  return (
    <section
      className={`rounded-2xl border border-white/5 bg-bg-panel/80 backdrop-blur p-5 shadow-xl shadow-black/20 ${className}`}
    >
      {(title || right) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-sm font-medium uppercase tracking-wider text-ink-dim">{title}</h2>}
            {subtitle && <p className="mt-1 text-xs text-ink-faint">{subtitle}</p>}
          </div>
          {right && <div className="shrink-0">{right}</div>}
        </header>
      )}
      {children}
    </section>
  )
}
