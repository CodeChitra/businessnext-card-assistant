import { act, fireEvent, render, screen, within } from '@testing-library/react'

import type { AgentResponse } from '../api/types'
import { AgentAnswer } from './AgentAnswer'
import { AnswerMarkdown } from './AnswerMarkdown'

const MESSAGE =
  'Here’s how a credit limit increase works for your card:\n\n' +
  '- **Eligibility checks:** We can consider a request if the account meets our policy criteria.\n' +
  '- **Income assessment is required:** A credit officer must first assess your income before any decision is made.\n' +
  '- **If a request is declined:** We’ll give a plain-language reason within 7 days.\n\n' +
  'If you’d like, I can submit a limit increase request for review.'

const response: AgentResponse = {
  behaviour: 'answer',
  message: MESSAGE,
  claims: [
    { text: 'A request can be considered if the account meets the policy criteria', citations: [{ type: 'policy', ref: 'POL-CRD-001#1' }] },
    { text: 'A credit officer must assess income before any decision is made', citations: [{ type: 'policy', ref: 'POL-CRD-002#body' }] },
    { text: 'A plain-language reason is given within 7 days of a decline', citations: [{ type: 'policy', ref: 'POL-CRD-001#4' }] },
  ],
  reason_codes: [],
  service_request: null,
  degraded: false,
  follow_ups: [],
  meta: {
    model: null,
    prompt_versions: {},
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
    latency_ms: 0,
    trace_id: null,
    thread_id: 't1',
    fallback_used: false,
    repaired: false,
    safe_fallback: false,
    retrieval_miss: false,
    rules_fired: [],
  },
}

const noop = () => {}

describe('markdown answers', () => {
  it('renders bullets as a list, not one collapsed paragraph', () => {
    render(<AgentAnswer response={response} selectedClaim={null} onSelectClaim={noop} onShowSources={noop} />)
    const items = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(within(items[0]!).getByText('Eligibility checks:').tagName).toBe('STRONG')
    expect(screen.getByText(/Here’s how a credit limit increase works/).tagName).toBe('P')
    expect(screen.getByText(/I can submit a limit increase request/).tagName).toBe('P')
  })

  it('puts each citation marker inside the bullet it supports, and it still opens evidence', () => {
    const onSelect = vi.fn()
    render(<AgentAnswer response={response} selectedClaim={null} onSelectClaim={onSelect} onShowSources={noop} />)
    const items = screen.getAllByRole('listitem')
    expect(within(items[0]!).getByRole('button', { name: 'Show source 1' })).toBeInTheDocument()
    expect(within(items[1]!).getByRole('button', { name: 'Show source 2' })).toBeInTheDocument()
    expect(within(items[2]!).getByRole('button', { name: 'Show source 3' })).toBeInTheDocument()
    fireEvent.click(within(items[1]!).getByRole('button', { name: 'Show source 2' }))
    expect(onSelect).toHaveBeenCalledWith(2)
  })

  it('never renders HTML, images or links from the model', () => {
    const { container } = render(
      <AnswerMarkdown
        source={'Safe text <script>alert(1)</script> <img src=x onerror=alert(1)> [click](http://evil.example) ![pic](http://evil.example/p.png) <b>bold</b>'}
        selectedClaim={null}
        onSelectClaim={noop}
        interactive
      />,
    )
    for (const tag of ['script', 'img', 'a', 'b', 'iframe']) {
      expect(container.querySelector(tag)).toBeNull()
    }
    expect(container).toHaveTextContent('Safe text')
    expect(container).toHaveTextContent('click') // link text survives, the link does not
  })

  it('drops headings and tables to plain text rather than styling them', () => {
    const { container } = render(
      <AnswerMarkdown source={'# Big heading\n\n| a | b |\n|---|---|\n| 1 | 2 |'} selectedClaim={null} onSelectClaim={noop} interactive />,
    )
    expect(container.querySelector('h1,table')).toBeNull()
    expect(container).toHaveTextContent('Big heading')
  })
})

describe('progressive reveal', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  const withFollowUps = { ...response, follow_ups: ['Can I see my reasons?'] }

  it('reveals the validated text, holds back the extras, then completes', () => {
    render(
      <AgentAnswer response={withFollowUps} selectedClaim={null} onSelectClaim={noop} onShowSources={noop} animate showFollowUps onFollowUp={noop} />,
    )
    // Mid-reveal: screen readers get the full text once; no interactive markers, no extras yet.
    expect(screen.getByText(/Here’s how a credit limit/, { selector: '.sr-only' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Show source/ })).not.toBeInTheDocument()
    expect(screen.queryByText('You might also ask')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /How this answer was determined/ })).not.toBeInTheDocument()

    act(() => void vi.advanceTimersByTime(5000))

    expect(screen.getAllByRole('button', { name: /Show source/ })).toHaveLength(3)
    expect(screen.getByRole('button', { name: /How this answer was determined/ })).toBeInTheDocument()
    expect(screen.getByText('You might also ask')).toBeInTheDocument()
    expect(screen.queryByText('Show full answer')).not.toBeInTheDocument()
  })

  it('"Show full answer" completes it at once', () => {
    render(<AgentAnswer response={response} selectedClaim={null} onSelectClaim={noop} onShowSources={noop} animate />)
    fireEvent.click(screen.getByRole('button', { name: 'Show full answer' }))
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
    expect(screen.getAllByRole('button', { name: /Show source/ })).toHaveLength(3)
  })

  it('is instant for reduced motion', () => {
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: q.includes('prefers-reduced-motion'),
      addEventListener: () => {},
      removeEventListener: () => {},
    }))
    render(<AgentAnswer response={response} selectedClaim={null} onSelectClaim={noop} onShowSources={noop} animate />)
    expect(screen.getAllByRole('button', { name: /Show source/ })).toHaveLength(3)
    expect(screen.queryByText('Show full answer')).not.toBeInTheDocument()
  })
})

describe('follow-up questions', () => {
  const withFollowUps = { ...response, follow_ups: ['Can I see my reasons?', 'What documents do I need?'] }

  it('sends the exact question when chosen', () => {
    const onFollowUp = vi.fn()
    render(
      <AgentAnswer response={withFollowUps} selectedClaim={null} onSelectClaim={noop} onShowSources={noop} showFollowUps onFollowUp={onFollowUp} />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'What documents do I need?' }))
    expect(onFollowUp).toHaveBeenCalledWith('What documents do I need?')
  })

  it('is hidden when there are none, or when this is not the latest answer', () => {
    const { rerender } = render(
      <AgentAnswer response={response} selectedClaim={null} onSelectClaim={noop} onShowSources={noop} showFollowUps onFollowUp={noop} />,
    )
    expect(screen.queryByText('You might also ask')).not.toBeInTheDocument()
    rerender(
      <AgentAnswer response={withFollowUps} selectedClaim={null} onSelectClaim={noop} onShowSources={noop} onFollowUp={noop} />,
    )
    expect(screen.queryByText('You might also ask')).not.toBeInTheDocument()
  })

  it('is disabled while another message is being answered', () => {
    render(
      <AgentAnswer response={withFollowUps} selectedClaim={null} onSelectClaim={noop} onShowSources={noop} showFollowUps followUpsDisabled onFollowUp={noop} />,
    )
    expect(screen.getByRole('button', { name: 'Can I see my reasons?' })).toBeDisabled()
  })
})
