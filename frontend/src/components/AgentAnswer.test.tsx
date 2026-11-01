import { fireEvent, render, screen } from '@testing-library/react'

import type { AgentResponse } from '../api/types'
import { AgentAnswer } from './AgentAnswer'

const meta: AgentResponse['meta'] = {
  model: 'openai:gpt-5',
  prompt_versions: {},
  input_tokens: 2400,
  output_tokens: 300,
  cost_usd: 0.006,
  latency_ms: 7400,
  trace_id: null,
  thread_id: 't1',
  fallback_used: false,
  repaired: false,
  safe_fallback: false,
  retrieval_miss: false,
  rules_fired: [],
}

const fee: AgentResponse = {
  behaviour: 'answer',
  message: 'Your card-year spend is 1,62,000. The Signature fee is waived at 4,00,000.',
  claims: [
    { text: 'Card-year spend is 1,62,000', citations: [{ type: 'account', ref: 'account.card_year_spend' }] },
    { text: 'Signature annual fee waived on spend of 4,00,000', citations: [{ type: 'policy', ref: 'POL-FEE-007#body' }] },
  ],
  reason_codes: [],
  service_request: null,
  degraded: false,
  follow_ups: [],
  meta,
}

const noop = () => {}

describe('AgentAnswer', () => {
  it('numbers each sourced sentence and reports the selected marker', () => {
    const onSelect = vi.fn()
    render(<AgentAnswer response={fee} selectedClaim={null} onSelectClaim={onSelect} onShowSources={noop} />)
    fireEvent.click(screen.getByRole('button', { name: 'Show source 2' }))
    expect(onSelect).toHaveBeenCalledWith(2)
    expect(screen.getByRole('button', { name: /How this answer was determined/ })).toHaveTextContent('(2 sources)')
    expect(screen.queryByLabelText('Outcome')).not.toBeInTheDocument() // answers have no decision block
  })

  it('shows a decline with plain-language reasons', () => {
    render(
      <AgentAnswer
        response={{ ...fee, behaviour: 'decline_with_reason', reason_codes: ['AA04'] }}
        selectedClaim={null}
        onSelectClaim={noop}
        onShowSources={noop}
      />,
    )
    expect(screen.getByText('Not possible right now')).toBeInTheDocument()
    expect(screen.getByText(/An open dispute on the account/)).toBeInTheDocument()
    expect(screen.queryByText('(AA04)')).not.toBeInTheDocument() // internal codes are developer-only
  })

  it('shows reason codes only with developer details on', () => {
    render(
      <AgentAnswer
        response={{ ...fee, behaviour: 'decline_with_reason', reason_codes: ['AA04'] }}
        selectedClaim={null}
        onSelectClaim={noop}
        onShowSources={noop}
        devDetails
      />,
    )
    expect(screen.getByText('(AA04)')).toBeInTheDocument()
  })

  it('opens the evidence for the whole answer', () => {
    const onShow = vi.fn()
    render(<AgentAnswer response={fee} selectedClaim={null} onSelectClaim={noop} onShowSources={onShow} />)
    fireEvent.click(screen.getByRole('button', { name: /How this answer was determined/ }))
    expect(onShow).toHaveBeenCalledOnce()
  })

  it('moves the request confirmation out of the prose into a receipt', () => {
    render(
      <AgentAnswer
        response={{
          ...fee,
          behaviour: 'raise_request',
          message:
            "We'll look into the payment.\n\nI've raised request SR-1234ABCD (transaction dispute). You can expect an update within 2 working days.",
          service_request: { request_id: 'SR-1234ABCD', queue: 'DISPUTES', sla_hours: 16 },
        }}
        selectedClaim={null}
        onSelectClaim={noop}
        onShowSources={noop}
      />,
    )
    expect(screen.getByText('SR-1234ABCD')).toBeInTheDocument()
    expect(screen.getByText('Disputes')).toBeInTheDocument()
    expect(screen.getByText('2 working days')).toBeInTheDocument()
    expect(screen.queryByText(/I've raised request/)).not.toBeInTheDocument()
    expect(screen.getByText('Sent to a specialist')).toBeInTheDocument()
    expect(screen.getByText('Under review')).toBeInTheDocument()
  })

  it('titles a routed refusal as a hand-off, and never shows a case without a request id', () => {
    const { rerender } = render(
      <AgentAnswer
        response={{
          ...fee,
          behaviour: 'refuse',
          service_request: { request_id: 'SR-77', queue: 'GENERAL', sla_hours: 8 },
        }}
        selectedClaim={null}
        onSelectClaim={noop}
        onShowSources={noop}
      />,
    )
    expect(screen.getByText('A specialist needs to confirm this')).toBeInTheDocument()
    rerender(
      <AgentAnswer response={{ ...fee, behaviour: 'refuse' }} selectedClaim={null} onSelectClaim={noop} onShowSources={noop} />,
    )
    expect(screen.queryByText('Under review')).not.toBeInTheDocument()
    // A plain refusal already says so in its message; no extra panel repeating it.
    expect(screen.queryByLabelText('Outcome')).not.toBeInTheDocument()
    expect(screen.queryByText('Under review')).not.toBeInTheDocument()
  })

  it('explains degraded mode and safe fallback in plain words', () => {
    render(
      <AgentAnswer
        response={{ ...fee, degraded: true, meta: { ...meta, safe_fallback: true } }}
        selectedClaim={null}
        onSelectClaim={noop}
        onShowSources={noop}
      />,
    )
    const notes = screen.getAllByRole('status').map((n) => n.textContent)
    expect(notes.some((t) => t?.includes('general policy only'))).toBe(true)
    expect(notes.some((t) => t?.includes('instead of guessing'))).toBe(true)
  })
})
