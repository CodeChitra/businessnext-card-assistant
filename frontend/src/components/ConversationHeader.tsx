import type { CustomerSummary } from '../api/types'
import type { Theme } from '../hooks/usePreferences'
import { LockIcon, MenuIcon, MoonIcon, PanelIcon, SunIcon } from './icons'

interface Props {
  current: CustomerSummary | null
  showMenu: boolean
  onMenu: () => void
  detailsOpen: boolean
  detailsAvailable: boolean
  onDetails: () => void
  theme: Theme
  onTheme: () => void
}

const ICON_BUTTON =
  'grid h-10 w-10 place-items-center rounded-control text-muted hover:bg-sunk hover:text-ink disabled:opacity-40 disabled:hover:bg-transparent'

export function ConversationHeader(p: Props) {
  return (
    <header className="flex min-h-14 shrink-0 items-center justify-between gap-2 border-b border-line bg-paper px-2 sm:px-4">
      <div className="flex min-w-0 items-center gap-1.5">
        {p.showMenu && (
          <button type="button" onClick={p.onMenu} aria-label="Open menu" className={ICON_BUTTON}>
            <MenuIcon />
          </button>
        )}
        <div className="min-w-0 px-1">
          {p.current ? (
            <>
              <p className="truncate leading-tight font-medium">{p.current.card_product} card</p>
              <p className="truncate text-xs text-muted">{p.current.name}</p>
            </>
          ) : (
            <p className="truncate text-muted">No cardholder selected</p>
          )}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {p.current && (
          <p className="mr-1 flex items-center gap-1.5 text-sm text-muted" title="Secure session">
            <LockIcon width={15} height={15} className="text-teal" />
            <span className="max-sm:sr-only">Secure session</span>
          </p>
        )}
        <button
          type="button"
          onClick={p.onDetails}
          disabled={!p.detailsAvailable}
          aria-expanded={p.detailsOpen}
          aria-label="How this answer was determined"
          title="How this answer was determined"
          className={`${ICON_BUTTON} ${p.detailsOpen ? 'bg-teal-wash text-teal' : ''}`}
        >
          <PanelIcon />
        </button>
        <button
          type="button"
          onClick={p.onTheme}
          aria-label={`Switch to ${p.theme === 'dark' ? 'light' : 'dark'} theme`}
          title={`Switch to ${p.theme === 'dark' ? 'light' : 'dark'} theme`}
          className={ICON_BUTTON}
        >
          {p.theme === 'dark' ? <SunIcon /> : <MoonIcon />}
        </button>
      </div>
    </header>
  )
}
