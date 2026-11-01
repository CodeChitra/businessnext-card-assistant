import type { AgentResponse, Citation } from '../api/types'
import { usePolicyChunk } from '../hooks/usePolicyChunk'
import { SOURCE_GROUP, fieldLabel } from '../lib/format'
import { bestUnit, parsePolicy } from '../lib/policyText'
import { CloseIcon } from './icons'
import { PolicyText } from './PolicyText'

interface Props {
  response: AgentResponse | null
  selectedClaim: number | null
  onSelectClaim: (n: number) => void
  onClose: () => void
  devDetails: boolean
}

const GROUP_ORDER: Citation['type'][] = ['account', 'policy', 'rule']

export function EvidenceDrawer({ response, selectedClaim, onSelectClaim, onClose, devDetails }: Props) {
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
        <h2 id="evidence-title" tabIndex={-1} data-autofocus className="font-semibold outline-none">
          How this answer was determined
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close details"
          className="grid h-10 w-10 place-items-center rounded-control text-muted hover:bg-sunk hover:text-ink"
        >
          <CloseIcon />
        </button>
      </header>
      <div className="flex-1 overflow-y-auto px-5 py-5">
        {!response ? (
          <EmptyNote title="Nothing selected yet">
            Ask a question, then choose “How this answer was determined” to see where it came from.
          </EmptyNote>
        ) : response.claims.length === 0 ? (
          <EmptyNote title="No evidence available">
            This reply doesn’t state any facts about your card or our policies, so there is nothing
            to trace.
          </EmptyNote>
        ) : (
          <>
            <p className="mb-5 text-[0.9375rem] text-muted">
              Every numbered statement is checked against your card account, card policy or a fixed
              decision rule before you see it. Choose one to see its source.
            </p>
            <ol className="space-y-1">
              {response.claims.map((claim, i) => {
                const n = i + 1
                const open = selectedClaim === n
                const groups = GROUP_ORDER.map((type) => ({
                  type,
                  items: claim.citations.filter((c) => c.type === type),
                })).filter((g) => g.items.length > 0)
                return (
                  <li key={n} className="relative">
                    <button
                      type="button"
                      onClick={() => onSelectClaim(n)}
                      aria-expanded={open}
                      className={`flex min-h-11 w-full gap-3 rounded-control px-2.5 py-2 text-left text-[0.9375rem] transition-colors duration-150 ${open ? 'bg-teal-wash' : 'hover:bg-sunk'}`}
                    >
                      <span
                        className={`figures mt-0.5 inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full text-[0.7rem] font-semibold ${open ? 'bg-teal text-on-accent' : 'bg-teal-wash text-teal'}`}
                      >
                        {n}
                      </span>
                      <span>{claim.text}</span>
                    </button>
                    {open && (
                      <div className="fade-in ml-[1.3rem] space-y-5 border-l border-teal/30 py-3 pr-1 pl-6">
                        {groups.map((g) => (
                          <section key={g.type}>
                            <h3 className="mb-1.5 text-sm font-medium text-teal">{SOURCE_GROUP[g.type]}</h3>
                            <div className="space-y-4">
                              {g.items.map((c) => (
                                <CitationSource key={c.ref} citation={c} claimText={claim.text} devDetails={devDetails} />
                              ))}
                            </div>
                          </section>
                        ))}
                      </div>
                    )}
                  </li>
                )
              })}
            </ol>
          </>
        )}
      </div>
    </div>
  )
}

function EmptyNote({ title, children }: { title: string; children: string }) {
  return (
    <div className="rounded-panel border border-dashed border-line px-4 py-5 text-center">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted">{children}</p>
    </div>
  )
}

function CitationSource({ citation, claimText, devDetails }: { citation: Citation; claimText: string; devDetails: boolean }) {
  if (citation.type === 'account') {
    return (
      <SourceNote title={fieldLabel(citation.ref)} dev={devDetails ? citation.ref : null}>
        Read from your account record when this answer was written.
      </SourceNote>
    )
  }
  if (citation.type === 'rule') {
    return (
      <SourceNote title={fieldLabel(citation.ref)} dev={devDetails ? citation.ref : null}>
        Decided or calculated by a fixed policy rule, not written by the assistant.
      </SourceNote>
    )
  }
  return <PolicyExcerpt key={citation.ref} id={citation.ref} claimText={claimText} devDetails={devDetails} />
}

function SourceNote({ title, dev, children }: { title: string; dev: string | null; children: string }) {
  return (
    <div className="text-sm">
      <div className="font-medium">{title}</div>
      <p className="text-muted">{children}</p>
      {dev && <p className="mt-0.5 text-xs text-muted">{dev}</p>}
    </div>
  )
}

function PolicyExcerpt({ id, claimText, devDetails }: { id: string; claimText: string; devDetails: boolean }) {
  const state = usePolicyChunk(id)
  if (state.status === 'loading') {
    return (
      <div className="space-y-2" aria-busy="true">
        <span className="sr-only">Loading policy text</span>
        <div className="h-3 w-2/3 rounded-full bg-sunk" />
        <div className="h-3 w-full rounded-full bg-sunk" />
        <div className="h-3 w-5/6 rounded-full bg-sunk" />
      </div>
    )
  }
  if (state.status === 'error')
    return <p className="text-sm text-red">The policy text couldn’t load. Choose the statement again to retry.</p>

  const { chunk } = state
  const blocks = parsePolicy(chunk.text)
  const hit = bestUnit(blocks, claimText)
  return (
    <figure className="text-sm">
      <figcaption>
        <div className="font-medium">
          {chunk.title}
          {chunk.heading ? <span className="font-normal text-muted">, {chunk.heading}</span> : null}
        </div>
        <div className="figures text-xs text-muted">
          {chunk.effective_date ? `Effective ${chunk.effective_date}, ` : ''}version {chunk.version}
          {devDetails ? `, ${chunk.doc_id}` : ''}
        </div>
      </figcaption>
      {chunk.trust === 'non_policy' && (
        <p className="mt-2 rounded-control bg-red-wash px-3 py-2 text-xs text-red">
          Informal notes, not governed policy. Never used to support an answer.
        </p>
      )}
      <blockquote className="mt-2.5 rounded-panel bg-mist px-3.5 py-3">
        <PolicyText blocks={blocks} highlight={hit} />
      </blockquote>
      {hit && <p className="mt-1.5 text-xs text-muted">Highlighted: the passage that supports this statement.</p>}
    </figure>
  )
}
