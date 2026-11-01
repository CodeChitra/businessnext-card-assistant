import { useId, useState } from 'react'

import type { CustomerSummary } from '../api/types'
import { initials } from '../lib/format'
import { ChevronIcon, LockIcon } from './icons'

interface Props {
  customers: CustomerSummary[]
  current: CustomerSummary | null
  onChoose: (id: string) => void
}

/** The signed-in account. Switching stands in for signing in as another demo cardholder. */
export function AccountSwitcher({ customers, current, onChoose }: Props) {
  const [open, setOpen] = useState(false)
  const listId = useId()

  return (
    <div
      className="border-t border-line p-3"
      onKeyDown={(e) => {
        if (e.key === 'Escape' && open) {
          e.stopPropagation()
          setOpen(false)
        }
      }}
    >
      {open && (
        <div id={listId} className="fade-in mb-2 max-h-72 overflow-y-auto rounded-panel border border-line bg-paper py-1">
          <p className="px-3 pt-1.5 pb-1 text-xs font-medium text-muted">Switch demo cardholder</p>
          <ul>
            {customers.map((c) => (
              <li key={c.customer_id}>
                <button
                  type="button"
                  aria-current={c.customer_id === current?.customer_id ? 'true' : undefined}
                  onClick={() => {
                    onChoose(c.customer_id)
                    setOpen(false)
                  }}
                  className="flex min-h-11 w-full items-center gap-2.5 px-3 py-1.5 text-left text-sm hover:bg-sunk aria-[current]:bg-navy-wash focus-visible:-outline-offset-2"
                >
                  <span className="min-w-0 flex-1 truncate">{c.name}</span>
                  <span className="shrink-0 text-xs text-muted">{c.card_product}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <button
        type="button"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((v) => !v)}
        disabled={customers.length === 0}
        className="flex min-h-14 w-full items-center gap-3 rounded-panel px-2 py-2 text-left hover:bg-sunk disabled:opacity-60"
      >
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-navy text-sm font-semibold text-paper">
          {current ? initials(current.name) : '?'}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{current?.name ?? 'Not signed in'}</span>
          <span className="block truncate text-xs text-muted">
            {current ? `${current.card_product} card` : 'Choose a demo cardholder'}
          </span>
          {current && (
            <span className="mt-0.5 flex items-center gap-1 text-xs text-muted">
              <LockIcon width={12} height={12} className="shrink-0 text-teal" />
              Secure session
            </span>
          )}
        </span>
        <ChevronIcon className={`shrink-0 text-muted transition-transform duration-150 ${open ? '-rotate-90' : 'rotate-0'}`} />
        <span className="sr-only">{open ? 'Hide cardholders' : 'Switch cardholder'}</span>
      </button>
    </div>
  )
}
