import type { ReactNode } from 'react'

import { useDialog } from '../hooks/useDialog'

interface Props {
  open: boolean
  side: 'left' | 'right'
  label: string
  onClose: () => void
  /** Docked sheets sit in the layout (no scrim, no focus trap); overlays are modal dialogs. */
  docked?: boolean
  className?: string
  children: ReactNode
}

export function Sheet({ open, side, label, onClose, docked = false, className = '', children }: Props) {
  const ref = useDialog<HTMLDivElement>(open, onClose, !docked)
  if (!open) return null

  if (docked) {
    return (
      <aside ref={ref} aria-label={label} className={`sheet-right h-full overflow-hidden border-l border-line bg-paper ${className}`}>
        {children}
      </aside>
    )
  }
  return (
    <div className="fixed inset-0 z-40">
      <div className="fade-in absolute inset-0 bg-scrim" onClick={onClose} aria-hidden />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        className={`absolute inset-y-0 flex flex-col overflow-hidden bg-paper shadow-sheet outline-none ${
          side === 'right' ? 'sheet-right right-0 border-l' : 'sheet-left left-0 border-r'
        } border-line ${className}`}
      >
        {children}
      </div>
    </div>
  )
}
