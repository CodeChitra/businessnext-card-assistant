import type { CustomerSummary, Health, Simulate } from '../api/types'
import { SCENARIO_GROUPS } from '../lib/scenarios'
import { SUGGESTIONS } from '../lib/suggestions'
import { AccountSwitcher } from './AccountSwitcher'
import { CardIcon, CloseIcon, PlusIcon, WrenchIcon } from './icons'

interface Props {
  customers: CustomerSummary[]
  current: CustomerSummary | null
  onCustomer: (id: string) => void
  onNewConversation: () => void
  onSuggest: (question: string) => void
  onScenario: (customerId: string, question: string) => void
  health: Health | null
  simulate: Simulate | null
  onSimulate: (s: Simulate | null) => void
  inspector: boolean
  onInspector: () => void
  onClose?: () => void // present when shown as a sheet
}

const SIMULATIONS: [Simulate | null, string][] = [
  [null, 'No failure'],
  ['timeout', 'Account service times out'],
  ['primary_down', 'Primary model is down'],
]

export function NavPanel(p: Props) {
  return (
    <nav aria-label="Card Assistant" className="flex h-full flex-col bg-paper">
      <div className="flex items-center gap-2.5 px-5 pt-5 pb-4">
        <span className="grid h-8 w-8 place-items-center rounded-control bg-navy text-paper" aria-hidden>
          <CardIcon width={17} height={17} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold leading-tight tracking-tight">Card Assistant</p>
          <p className="text-xs text-muted">Cards and payments</p>
        </div>
        {p.onClose && (
          <button
            type="button"
            onClick={p.onClose}
            aria-label="Close menu"
            className="grid h-10 w-10 place-items-center rounded-control text-muted hover:bg-sunk hover:text-ink"
          >
            <CloseIcon />
          </button>
        )}
      </div>

      <div className="px-3">
        <button
          type="button"
          onClick={p.onNewConversation}
          disabled={!p.current}
          className="flex min-h-11 w-full items-center justify-center gap-2 rounded-control bg-teal px-3 font-medium text-on-accent hover:bg-teal/90 disabled:opacity-40"
        >
          <PlusIcon />
          New conversation
        </button>
      </div>

      <div className="mt-5 flex-1 space-y-6 overflow-y-auto px-3 pb-4">
        <section>
          <h2 className="mb-1 px-2 text-xs font-medium text-muted">Shortcuts</h2>
          <ul>
            {SUGGESTIONS.map((s) => (
              <li key={s.label}>
                <button
                  type="button"
                  disabled={!p.current}
                  onClick={() => p.onSuggest(s.question)}
                  className="min-h-10 w-full rounded-control px-2 py-1.5 text-left text-[0.9375rem] hover:bg-sunk disabled:opacity-40"
                >
                  {s.label}
                </button>
              </li>
            ))}
          </ul>
        </section>

        <details className="group rounded-panel border border-dashed border-line">
          <summary className="flex min-h-10 cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm font-medium text-muted select-none">
            <WrenchIcon width={15} height={15} />
            Testing tools
            <span className="ml-auto text-xs font-normal group-open:hidden">Show</span>
            <span className="ml-auto hidden text-xs font-normal group-open:inline">Hide</span>
          </summary>
          <div className="space-y-5 border-t border-dashed border-line px-3 py-3">
            <label className="flex min-h-10 cursor-pointer items-center justify-between gap-3 text-sm">
              <span>
                <span className="block font-medium">Developer details</span>
                <span className="block text-xs text-muted">Pipeline, rules, model and cost per answer</span>
              </span>
              <input
                type="checkbox"
                role="switch"
                checked={p.inspector}
                onChange={p.onInspector}
                className="h-4 w-4 shrink-0 accent-[var(--teal)]"
              />
            </label>

            {SCENARIO_GROUPS.map((group) => (
              <section key={group.title}>
                <h3 className="mb-0.5 text-xs font-medium text-muted">{group.title}</h3>
                <ul>
                  {group.scenarios.map((s) => (
                    <li key={s.id}>
                      <button
                        type="button"
                        onClick={() => p.onScenario(s.customer, s.question)}
                        className="min-h-9 w-full rounded-control px-2 py-1 text-left text-sm hover:bg-sunk"
                      >
                        {s.title}
                        {p.inspector && <span className="ml-1 whitespace-nowrap text-xs text-muted">({s.id})</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))}

            {p.health?.demo_faults && (
              <fieldset>
                <legend className="mb-0.5 text-xs font-medium text-muted">Simulate a failure</legend>
                <p className="mb-1.5 text-xs text-muted">Applies to your next message only.</p>
                {SIMULATIONS.map(([value, label]) => (
                  <label key={label} className="flex min-h-8 items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="simulate"
                      className="accent-[var(--teal)]"
                      checked={p.simulate === value}
                      onChange={() => p.onSimulate(value)}
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
            )}

            {p.health && (
              <p className="figures text-xs leading-relaxed text-muted">
                Policies as of {p.health.as_of_date}. Answering with {p.health.models.primary}.
                {p.health.tracing.enabled ? ' Traces recorded.' : ''}
              </p>
            )}
          </div>
        </details>
      </div>

      <AccountSwitcher customers={p.customers} current={p.current} onChoose={p.onCustomer} />
    </nav>
  )
}
