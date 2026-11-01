import { fireEvent, render, screen } from '@testing-library/react'
import type { ComponentProps } from 'react'

import type { AgentResponse, CustomerSummary } from '../api/types'
import type { Turn } from '../hooks/useChat'
import { Conversation } from './Conversation'

const turns: Turn[] = [
  { id: 'a', role: 'customer', text: 'Markup in Singapore?' },
  {
    id: 'b',
    role: 'agent',
    status: 'streaming',
    steps: [{ step: 'retrieve', label: 'Searching our policies', sources_found: 3, miss: false }],
  },
]

const sai: CustomerSummary = { customer_id: 'CUST-1', name: 'Sai Rao', card_product: 'Classic' }

function setup(overrides: Partial<ComponentProps<typeof Conversation>> = {}) {
  const props: ComponentProps<typeof Conversation> = {
    turns,
    customer: sai,
    customers: [sai],
    customersLoading: false,
    inspector: false,
    selection: null,
    onSelect: vi.fn(),
    onSuggest: vi.fn(),
    onRetry: vi.fn(),
    onFollowUp: vi.fn(),
    followUpsDisabled: false,
    onChooseCustomer: vi.fn(),
    onGrow: vi.fn(),
    onEdit: vi.fn(),
    onReplay: vi.fn(),
    controlsDisabled: false,
    ...overrides,
  }
  return { props, ...render(<Conversation {...props} />) }
}

describe('Conversation', () => {
  it('never calls scrollIntoView (it would scroll the page, not just the conversation)', () => {
    const spy = vi.fn()
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = spy as unknown as typeof original
    try {
      const { rerender, props } = setup()
      expect(screen.getByText('Markup in Singapore?')).toBeInTheDocument()
      expect(screen.getByText('Applying policy rules')).toBeInTheDocument() // step now running
      rerender(<Conversation {...props} turns={[...turns, { id: 'c', role: 'customer', text: 'Hi' }]} />)
      expect(spy).not.toHaveBeenCalled()
      expect(props.onGrow).toHaveBeenCalled() // the scroller is told instead, and decides
    } finally {
      Element.prototype.scrollIntoView = original
    }
  })

  it('shows pipeline detail only when developer details are on', () => {
    const { rerender, props } = setup()
    expect(screen.queryByText('Developer details')).not.toBeInTheDocument()
    rerender(<Conversation {...props} inspector />)
    expect(screen.getByText('Developer details')).toBeInTheDocument()
    expect(screen.getByText(/3 documents/)).toBeInTheDocument()
  })

  it('greets the customer by first name and offers specific shortcuts', () => {
    const { props } = setup({ turns: [] })
    expect(screen.getByRole('heading', { name: 'Hello, Sai' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Check my credit limit/ }))
    expect(props.onSuggest).toHaveBeenCalledWith('What is my current credit limit?')
  })

  it('asks who is signing in when no cardholder is chosen', () => {
    const { props } = setup({ turns: [], customer: null })
    fireEvent.click(screen.getByRole('button', { name: /Sai Rao/ }))
    expect(props.onChooseCustomer).toHaveBeenCalledWith('CUST-1')
  })

  it('offers to resend a message that failed', () => {
    const { props } = setup({
      turns: [
        { id: 'a', role: 'customer', text: 'What is my limit?' },
        { id: 'b', role: 'agent', status: 'error', steps: [], error: 'The response ended early.' },
      ],
    })
    expect(screen.getByRole('alert')).toHaveTextContent('I couldn’t get an answer')
    fireEvent.click(screen.getByRole('button', { name: 'Try sending again' }))
    expect(props.onRetry).toHaveBeenCalledWith('What is my limit?')
  })

  describe('follow-up questions', () => {
    const response = (follow_ups: string[]): AgentResponse => ({
      behaviour: 'answer',
      message: 'Your limit is 1,20,000.',
      claims: [],
      reason_codes: [],
      service_request: null,
      degraded: false,
      follow_ups,
      meta: {
        model: null,
        prompt_versions: {},
        input_tokens: 0,
        output_tokens: 0,
        cost_usd: 0,
        latency_ms: 0,
        trace_id: null,
        thread_id: 't',
        fallback_used: false,
        repaired: false,
        safe_fallback: false,
        retrieval_miss: false,
        rules_fired: [],
      },
    })
    const done = (id: string, q: string): Turn[] => [
      { id: `c-${id}`, role: 'customer', text: 'Q' },
      { id, role: 'agent', status: 'done', steps: [], response: response([q]) },
    ]

    it('are offered on the newest answer only', () => {
      setup({ turns: [...done('a1', 'Old question?'), ...done('a2', 'New question?')] })
      expect(screen.getByRole('button', { name: 'New question?' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Old question?' })).not.toBeInTheDocument()
    })

    it('are withheld while a newer message is still being answered', () => {
      setup({
        turns: [
          ...done('a1', 'Old question?'),
          { id: 'c2', role: 'customer', text: 'Next' },
          { id: 'a2', role: 'agent', status: 'streaming', steps: [] },
        ],
      })
      expect(screen.queryByRole('button', { name: 'Old question?' })).not.toBeInTheDocument()
    })

    it('send the chosen question', () => {
      const { props } = setup({ turns: done('a1', 'What fees apply?') })
      fireEvent.click(screen.getByRole('button', { name: 'What fees apply?' }))
      expect(props.onFollowUp).toHaveBeenCalledWith('What fees apply?')
    })
  })
})
