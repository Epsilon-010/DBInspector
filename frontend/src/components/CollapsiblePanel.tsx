import { useState, type ReactNode } from 'react'

export interface CollapsiblePanelProps {
  defaultOpen: boolean
  summary: string
  children: ReactNode
}

export function CollapsiblePanel({ defaultOpen, summary, children }: CollapsiblePanelProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <details
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
      className="group rounded-xl border border-white/10 bg-bg-panel/60"
    >
      <summary className="cursor-pointer list-none px-4 py-2 text-xs text-ink-dim hover:text-ink transition flex items-center justify-between">
        <span>{summary}</span>
        <span className="text-ink-faint group-open:rotate-180 transition-transform">▾</span>
      </summary>
      <div className="border-t border-white/10 p-4">{children}</div>
    </details>
  )
}
