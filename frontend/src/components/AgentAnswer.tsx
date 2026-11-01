import { useEffect, useId, useMemo, useRef } from 'react'

import type { AgentResponse } from '../api/types'
import { useReveal } from '../hooks/useReveal'
import { markSource, plainText } from '../lib/citationMarkers'
import { DECISION_TITLE, HANDOFF_TITLE, REASON_CODE_LABEL } from '../lib/format'
import { AnswerMarkdown } from './AnswerMarkdown'
import { SupportCaseCard } from './SupportCaseCard'

interface Props {
  response: AgentResponse
  selectedClaim: number | null // 1-based
  onSelectClaim: (n: number) => void
  onShowSources: () => void
  devDetails?: boolean
  /** Reveal the (already validated) text progressively; only for an answer that just arrived. */
  animate?: boolean
  /** True on the latest finished answer, the only one that offers follow-up questions. */
  showFollowUps?: boolean
  followUpsDisabled?: boolean
  onFollowUp?: (question: string) => void
  /** True while the answer is still being revealed (edit and replay wait until it is done). */
  onRevealingChange?: (revealing: boolean) => void
}

export function AgentAnswer({
  response,
  selectedClaim,
  onSelectClaim,
  onShowSources,
  devDetails = false,
  animate = false,
  showFollowUps = false,
  followUpsDisabled = false,
  onFollowUp,
  onRevealingChange,
}: Props) {
  // The system appends the request confirmation; the receipt shows it, so drop it from prose.
  const prose = response.service_request
    ? response.message.replace(/\n*I've raised request SR-[A-Z0-9]+[^\n]*$/, '').trimEnd()
    : response.message
  const marked = useMemo(
    () => markSource(prose, response.claims.map((c) => c.text)),
    [prose, response.claims],
  )
  const reveal = useReveal(marked, animate)
  const report = useRef(onRevealingChange)
  useEffect(() => {
    report.current = onRevealingChange
  })
  useEffect(() => {
    report.current?.(!reveal.done)
    return () => report.current?.(false)
  }, [reveal.done])
  const labelId = useId()
  const sources = response.claims.length
  const sr = response.service_request
  const followUps = showFollowUps && onFollowUp ? (response.follow_ups ?? []) : []

  return (
    <div className="space-y-4">
      {response.degraded && (
        <Notice>
          I couldn’t reach your account details just now, so this answer uses general policy
          only. Ask again in a moment for an answer about your account.
        </Notice>
      )}
      {response.meta.safe_fallback && (
        <Notice>
          I couldn’t verify an answer, so I’ve passed your question to the support team instead
          of guessing.
        </Notice>
      )}

      {/* While revealing, screen readers get the whole answer once instead of fragments. */}
      <div
        aria-hidden={!reveal.done || undefined}
        onClick={reveal.done ? undefined : reveal.skip}
        className={reveal.done ? undefined : 'cursor-pointer'}
      >
        <AnswerMarkdown
          source={reveal.text}
          selectedClaim={selectedClaim}
          onSelectClaim={onSelectClaim}
          interactive={reveal.done}
        />
      </div>
      {!reveal.done && (
        <>
          <p className="sr-only">{plainText(marked)}</p>
          <button
            type="button"
            onClick={reveal.skip}
            className="min-h-9 rounded-control text-sm text-muted underline decoration-line underline-offset-4 hover:text-ink"
          >
            Show full answer
          </button>
        </>
      )}

      {reveal.done && (
        <div className={`space-y-4 ${animate ? 'fade-in' : ''}`}>
        {sr ? (
          <SupportCaseCard
            request={sr}
            title={response.behaviour === 'raise_request' ? DECISION_TITLE.raise_request : HANDOFF_TITLE}
          />
        ) : (
          // A panel only where it adds something. A plain refusal (an out-of-scope question)
          // already says so in the message, so a box repeating it is noise.
          response.behaviour !== 'answer' &&
          (response.behaviour === 'decline_with_reason' || response.reason_codes.length > 0) && (
            <section
              aria-label="Outcome"
              className="max-w-[34rem] rounded-panel border border-line bg-paper px-4 py-3"
            >
              <h3 className="flex items-center gap-2 font-semibold">
                <span
                  className={`h-2.5 w-2.5 shrink-0 rounded-[2px] ${response.behaviour === 'decline_with_reason' ? 'bg-navy' : 'border-2 border-muted'}`}
                  aria-hidden
                />
                {DECISION_TITLE[response.behaviour]}
              </h3>
              {response.reason_codes.length > 0 && (
                <>
                  <p className="mt-2 text-sm text-muted">Why</p>
                  <ul className="mt-0.5 space-y-0.5">
                    {response.reason_codes.map((code) => (
                      <li key={code}>
                        {REASON_CODE_LABEL[code]}
                        {devDetails && <span className="ml-1 text-sm text-muted">({code})</span>}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )
        )}

        {sources > 0 && (
          <button
            type="button"
            onClick={onShowSources}
            className="group inline-flex min-h-9 items-center gap-1.5 rounded-control text-[0.9375rem] font-medium text-teal"
          >
            <span className="underline decoration-teal/40 underline-offset-4 group-hover:decoration-teal">
              How this answer was determined
            </span>{' '}
            <span className="figures font-normal text-muted">
              ({sources === 1 ? '1 source' : `${sources} sources`})
            </span>
          </button>
        )}

        {followUps.length > 0 && (
          <section aria-labelledby={`${labelId}-label`}>
            <p id={`${labelId}-label`} className="mb-2 text-sm text-muted">
              You might also ask
            </p>
            <ul className="flex flex-wrap gap-2">
              {followUps.map((q) => (
                <li key={q} className="max-w-full">
                  <button
                    type="button"
                    disabled={followUpsDisabled}
                    onClick={() => onFollowUp?.(q)}
                    className="min-h-11 max-w-full rounded-control border border-line bg-paper px-3.5 py-2 text-left text-[0.9375rem] hover:border-teal disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-line"
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
        </div>
      )}
    </div>
  )
}

function Notice({ children }: { children: string }) {
  return (
    <p role="status" className="flex max-w-[68ch] gap-2.5 text-[0.9375rem] text-ink">
      <span className="mt-[0.55em] h-2 w-2 shrink-0 rounded-full border-2 border-amber" aria-hidden />
      <span>
        <span className="font-medium text-amber">Limited answer. </span>
        {children}
      </span>
    </p>
  )
}

export function StatusLine({ label }: { label: string }) {
  return (
    <div className="space-y-3">
      <p className="flex items-center gap-2.5 text-muted" aria-live="polite">
        <span className="status-pulse inline-block h-2 w-2 rounded-full bg-teal" aria-hidden />
        {label}
      </p>
      <div className="max-w-[68ch] space-y-2" aria-hidden>
        <div className="h-3 w-[92%] rounded-full bg-sunk" />
        <div className="h-3 w-[64%] rounded-full bg-sunk" />
      </div>
    </div>
  )
}
