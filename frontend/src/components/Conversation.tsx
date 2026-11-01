import { type ReactNode, useEffect, useRef, useState } from 'react'

import type { CustomerSummary } from '../api/types'
import type { AgentTurn, Turn } from '../hooks/useChat'
import { initials } from '../lib/format'
import { raisedFrom } from '../lib/turns'
import { SUGGESTIONS } from '../lib/suggestions'
import { AgentAnswer, StatusLine } from './AgentAnswer'
import { EditableMessage } from './EditableMessage'
import { ChevronIcon, WrenchIcon } from './icons'
import { Inspector } from './Inspector'
import { ReplayAnswer } from './ReplayAnswer'

// Progress events mark finished steps; the status line names the step now running. The server
// classifies the question first (so unrelated ones end quickly), then looks up the account.
const NOW_RUNNING: Record<string, string> = {
  input_guard: 'Understanding your question',
  classify: 'Checking your account',
  load_account: 'Searching our policies',
  retrieve: 'Applying policy rules',
  policy: 'Drafting an answer from the sources',
  generate: 'Checking every statement against its source',
  validate: 'Finishing up',
  repair: 'Re-checking the corrected answer',
  safe_fallback: 'Passing your question to a colleague',
  uncovered: 'Passing your question to a colleague',
  short_circuit: 'Finishing up',
  act: 'Finishing up',
}

export interface Selection {
  turnId: string
  claim: number | null
}

interface Props {
  turns: Turn[]
  customer: CustomerSummary | null
  customers: CustomerSummary[]
  customersLoading: boolean
  inspector: boolean
  selection: Selection | null
  onSelect: (s: Selection) => void
  onSuggest: (question: string) => void
  onRetry: (question: string) => void
  onFollowUp: (question: string) => void
  followUpsDisabled: boolean
  onChooseCustomer: (id: string) => void
  /** The conversation got taller; the scroller decides whether to follow. */
  onGrow: () => void
  /** Edit the customer message at `turnIndex`: discard it and everything after, send `text`. */
  onEdit: (turnIndex: number, text: string) => void
  /** Re-ask the customer message at `turnIndex` (the one the latest answer responded to). */
  onReplay: (turnIndex: number) => void
  /** The reader opened an editor above the end of the conversation. */
  onEditStart?: () => void
  /** An answer is in flight, or we are offline: editing and replaying wait. */
  controlsDisabled: boolean
}

export function Conversation(p: Props) {
  const log = useRef<HTMLDivElement>(null)
  // The turn whose answer is still being revealed; edit and replay wait for it.
  const [revealingId, setRevealingId] = useState<string | null>(null)
  const hasTurns = p.turns.length > 0
  const { onGrow } = p
  // Tell the scroller when the content grows (a new turn, a reveal tick, a late-loading
  // citation) so it can follow if the reader is at the bottom. Never scrollIntoView: that also
  // scrolls every ancestor, including the page.
  useEffect(() => {
    const node = log.current
    if (!node) return
    onGrow()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => onGrow())
    observer.observe(node)
    return () => observer.disconnect()
  }, [hasTurns, p.turns, onGrow])

  if (!p.customer) {
    return <ChooseCardholder customers={p.customers} loading={p.customersLoading} onChoose={p.onChooseCustomer} />
  }
  if (p.turns.length === 0) return <NewConversation customer={p.customer} onSuggest={p.onSuggest} />

  // Follow-ups and replay belong to the newest answer only.
  const latestAgent = [...p.turns].reverse().find((t) => t.role === 'agent')
  const editsDisabled = p.controlsDisabled || revealingId !== null

  return (
    <div
      ref={log}
      role="log"
      aria-label="Conversation"
      className="mx-auto flex max-w-[50rem] flex-col gap-8 px-4 py-8 sm:px-6"
    >
      {p.turns.map((turn, i) => {
        if (turn.role === 'customer') {
          return (
            <EditableMessage
              key={turn.id}
              text={turn.text}
              disabled={editsDisabled}
              raisedRequests={raisedFrom(p.turns, i)}
              onEdit={(text) => p.onEdit(i, text)}
              onOpen={p.onEditStart}
            />
          )
        }
        const questionIndex = p.turns.findLastIndex((t, j) => j < i && t.role === 'customer')
        const question = questionIndex >= 0 ? p.turns[questionIndex] : undefined
        return (
          <AssistantTurn key={turn.id} turn={turn}>
            {turn.simulate && (
              <p className="flex items-center gap-1.5 text-sm text-amber">
                <WrenchIcon width={14} height={14} />
                Simulated failure for this message:{' '}
                {turn.simulate === 'timeout' ? 'account service times out' : 'primary model down'}
              </p>
            )}
            {turn.status === 'streaming' && (
              <StatusLine
                label={
                  turn.steps.length
                    ? (NOW_RUNNING[turn.steps[turn.steps.length - 1]!.step] ?? 'Working')
                    : 'Reading your message'
                }
              />
            )}
            {turn.status === 'done' && turn.response && (
              <AgentAnswer
                response={turn.response}
                selectedClaim={p.selection?.turnId === turn.id ? p.selection.claim : null}
                onSelectClaim={(n) => p.onSelect({ turnId: turn.id, claim: n })}
                onShowSources={() => p.onSelect({ turnId: turn.id, claim: null })}
                devDetails={p.inspector}
                animate={turn.animate}
                showFollowUps={turn === latestAgent}
                followUpsDisabled={p.followUpsDisabled}
                onFollowUp={p.onFollowUp}
                onRevealingChange={(revealing) =>
                  setRevealingId((cur) => (revealing ? turn.id : cur === turn.id ? null : cur))
                }
              />
            )}
            {turn.status === 'error' && (
              <div role="alert" className="max-w-[68ch] space-y-2">
                <p className="font-semibold">I couldn’t get an answer</p>
                <p className="text-muted">
                  {turn.error} Your message wasn’t answered, and nothing about your account
                  changed.
                </p>
                {question && (
                  <button
                    type="button"
                    onClick={() => p.onRetry(question.role === 'customer' ? question.text : '')}
                    className="min-h-10 rounded-control border border-line bg-paper px-3.5 text-[0.9375rem] font-medium text-teal hover:border-teal"
                  >
                    Try sending again
                  </button>
                )}
              </div>
            )}
            {turn === latestAgent && turn.status !== 'streaming' && questionIndex >= 0 && (
              <div>
                <ReplayAnswer
                  disabled={editsDisabled}
                  raisedRequests={raisedFrom(p.turns, questionIndex)}
                  onReplay={() => p.onReplay(questionIndex)}
                />
              </div>
            )}
            {p.inspector && (turn.steps.length > 0 || turn.response) && (
              <Inspector steps={turn.steps} response={turn.response} />
            )}
          </AssistantTurn>
        )
      })}
    </div>
  )
}

type MarkerKind = 'working' | 'answer' | 'decline' | 'review' | 'hold' | 'error'

function markerFor(turn: AgentTurn): MarkerKind {
  if (turn.status === 'streaming') return 'working'
  if (turn.status === 'error' || !turn.response) return 'error'
  const r = turn.response
  if (r.service_request || r.degraded || r.meta.safe_fallback) return 'review'
  if (r.behaviour === 'decline_with_reason') return 'decline'
  if (r.behaviour === 'refuse') return 'hold'
  return 'answer'
}

// Shape and colour both change, so the rail never relies on colour alone.
const MARKER: Record<MarkerKind, { cls: string; label: string }> = {
  working: { cls: 'status-pulse rounded-full border-2 border-teal bg-paper', label: 'Checking' },
  answer: { cls: 'rounded-full bg-teal', label: 'Answered' },
  decline: { cls: 'rounded-[2px] bg-navy', label: 'Decision' },
  review: { cls: 'rounded-full border-2 border-amber bg-paper', label: 'Needs review' },
  hold: { cls: 'rounded-full border-2 border-muted bg-paper', label: 'Not answered here' },
  error: { cls: 'rotate-45 rounded-[1px] bg-red', label: 'Not answered' },
}

/** One assistant turn, anchored to the ledger rail. */
function AssistantTurn({ turn, children }: { turn: AgentTurn; children: ReactNode }) {
  const marker = MARKER[markerFor(turn)]
  return (
    <article className="grid grid-cols-[0.75rem_minmax(0,1fr)] gap-x-4 sm:gap-x-5" aria-label={`Card Assistant, ${marker.label.toLowerCase()}`}>
      <div className="relative flex justify-center" aria-hidden>
        <span className="absolute top-5 bottom-0 w-px bg-teal/25" />
        <span className={`relative mt-[0.45rem] h-2.5 w-2.5 ${marker.cls}`} />
      </div>
      <div className="min-w-0 space-y-4">
        <p className="text-sm text-muted">
          <span className="mr-2 font-medium text-ink">Card Assistant</span>
          {marker.label}
        </p>
        {children}
      </div>
    </article>
  )
}

function NewConversation({ customer, onSuggest }: { customer: CustomerSummary; onSuggest: (q: string) => void }) {
  return (
    <div className="fade-in mx-auto flex min-h-full max-w-[50rem] flex-col justify-center px-4 py-10 sm:px-6">
      <h2 className="text-[1.75rem] leading-tight font-semibold tracking-tight">
        Hello, {customer.name.split(' ')[0]}
      </h2>
      <p className="mt-2 max-w-[60ch] text-muted">
        I can answer questions about your {customer.card_product} card, its fees and policies, and
        show you exactly where each answer comes from.
      </p>
      <h3 className="mt-8 mb-2 text-sm font-medium text-muted">Start with</h3>
      <ul className="divide-y divide-line overflow-hidden rounded-panel border border-line bg-paper">
        {SUGGESTIONS.map((s) => (
          <li key={s.label}>
            <button
              type="button"
              onClick={() => onSuggest(s.question)}
              className="group flex min-h-12 w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-sunk focus-visible:-outline-offset-2"
            >
              <span>
                <span className="block font-medium">{s.label}</span>
                <span className="block text-sm text-muted">{s.question}</span>
              </span>
              <ChevronIcon className="shrink-0 text-muted group-hover:text-teal" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ChooseCardholder({
  customers,
  loading,
  onChoose,
}: {
  customers: CustomerSummary[]
  loading: boolean
  onChoose: (id: string) => void
}) {
  return (
    <div className="mx-auto flex min-h-full max-w-[40rem] flex-col justify-center px-4 py-10 sm:px-6">
      <h2 className="text-[1.75rem] leading-tight font-semibold tracking-tight">Choose a demo cardholder</h2>
      <p className="mt-2 text-muted">
        This demo stands in for signing in. Pick a cardholder to start a session; every question
        is answered for that account only.
      </p>
      <ul
        className="mt-6 divide-y divide-line overflow-hidden rounded-panel border border-line bg-paper"
        aria-busy={loading}
        aria-label="Demo cardholders"
      >
        {loading
          ? [0, 1, 2, 3].map((i) => (
              <li key={i} className="flex items-center gap-3 px-4 py-3" aria-hidden>
                <span className="h-9 w-9 rounded-full bg-sunk" />
                <span className="h-3 w-40 rounded-full bg-sunk" />
              </li>
            ))
          : customers.map((c) => (
              <li key={c.customer_id}>
                <button
                  type="button"
                  onClick={() => onChoose(c.customer_id)}
                  className="group flex min-h-14 w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-sunk focus-visible:-outline-offset-2"
                >
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-navy-wash text-sm font-semibold text-navy">
                    {initials(c.name)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{c.name}</span>
                    <span className="block text-sm text-muted">{c.card_product} card</span>
                  </span>
                  <ChevronIcon className="shrink-0 text-muted group-hover:text-teal" />
                </button>
              </li>
            ))}
      </ul>
      {loading && <p className="sr-only" role="status">Loading cardholders</p>}
    </div>
  )
}
