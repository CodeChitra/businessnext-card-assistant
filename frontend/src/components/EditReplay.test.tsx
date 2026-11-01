import { fireEvent, render, screen, within } from '@testing-library/react'
import type { ComponentProps } from 'react'

import type { AgentResponse, CustomerSummary } from '../api/types'
import type { AgentTurn, Turn } from '../hooks/useChat'
import { Conversation } from './Conversation'

const sai: CustomerSummary = { customer_id: 'CUST-1', name: 'Sai Rao', card_product: 'Classic' }

const meta: AgentResponse['meta'] = {
  model: 'm',
  prompt_versions: {},
  input_tokens: 1,
  output_tokens: 1,
  cost_usd: 0,
  latency_ms: 1,
  trace_id: null,
  thread_id: 't',
  fallback_used: false,
  repaired: false,
  safe_fallback: false,
  retrieval_miss: false,
  rules_fired: [],
}

function answered(id: string, message: string, sr = false): AgentTurn {
  return {
    id,
    role: 'agent',
    status: 'done',
    steps: [],
    response: {
      behaviour: sr ? 'raise_request' : 'answer',
      message,
      claims: [],
      reason_codes: [],
      service_request: sr ? { request_id: 'SR-1A2B3C4D', queue: 'DISPUTES', sla_hours: 16 } : null,
      degraded: false,
      follow_ups: [],
      meta,
    },
  }
}

// 0 customer, 1 answer, 2 customer, 3 answer (the latest)
function exchange(secondRaisedRequest = false, firstRaisedRequest = false): Turn[] {
  return [
    { id: 'c1', role: 'customer', text: 'What is my limit?' },
    answered('a1', 'Your limit is 1,20,000.', firstRaisedRequest),
    { id: 'c2', role: 'customer', text: 'Someone used my card' },
    answered('a2', 'We will look into it.', secondRaisedRequest),
  ]
}

function setup(turns: Turn[], overrides: Partial<ComponentProps<typeof Conversation>> = {}) {
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

const editButtons = () => screen.getAllByRole('button', { name: 'Edit message' })

describe('editing a customer message', () => {
  it('opens an editor prefilled with the message and focuses it', () => {
    setup(exchange())
    expect(editButtons()).toHaveLength(2)
    fireEvent.click(editButtons()[1]!)
    const box = screen.getByRole('textbox', { name: 'Edit your message' })
    expect(box).toHaveValue('Someone used my card')
    expect(box).toHaveFocus()
  })

  it('tells the scroller to stop following when an editor opens', () => {
    const onEditStart = vi.fn()
    setup(exchange(), { onEditStart })
    fireEvent.click(editButtons()[1]!)
    expect(onEditStart).toHaveBeenCalledOnce()
  })

  it('cancels with Escape and returns focus to the Edit button', () => {
    setup(exchange())
    fireEvent.click(editButtons()[1]!)
    fireEvent.keyDown(screen.getByRole('textbox', { name: 'Edit your message' }), { key: 'Escape' })
    expect(screen.queryByRole('textbox', { name: 'Edit your message' })).not.toBeInTheDocument()
    expect(editButtons()[1]).toHaveFocus()
  })

  it('cancels with the Cancel button too', () => {
    const { props } = setup(exchange())
    fireEvent.click(editButtons()[0]!)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('textbox', { name: 'Edit your message' })).not.toBeInTheDocument()
    expect(props.onEdit).not.toHaveBeenCalled()
  })

  it('sends on Enter with the turn index and the new text', () => {
    const { props } = setup(exchange())
    fireEvent.click(editButtons()[1]!)
    const box = screen.getByRole('textbox', { name: 'Edit your message' })
    fireEvent.change(box, { target: { value: '  Someone used my card in Pune  ' } })
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(props.onEdit).toHaveBeenCalledWith(2, 'Someone used my card in Pune')
  })

  it('uses the right turn index for the first message', () => {
    const { props } = setup(exchange())
    fireEvent.click(editButtons()[0]!)
    fireEvent.change(screen.getByRole('textbox', { name: 'Edit your message' }), {
      target: { value: 'What is my available credit?' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send edited message' }))
    expect(props.onEdit).toHaveBeenCalledWith(0, 'What is my available credit?')
  })

  it('keeps Shift+Enter for a new line', () => {
    const { props } = setup(exchange())
    fireEvent.click(editButtons()[0]!)
    const box = screen.getByRole('textbox', { name: 'Edit your message' })
    fireEvent.change(box, { target: { value: 'changed' } })
    fireEvent.keyDown(box, { key: 'Enter', shiftKey: true })
    expect(props.onEdit).not.toHaveBeenCalled()
  })

  it('cannot send an unchanged or empty message', () => {
    const { props } = setup(exchange())
    fireEvent.click(editButtons()[0]!)
    const send = screen.getByRole('button', { name: 'Send edited message' })
    const box = screen.getByRole('textbox', { name: 'Edit your message' })
    expect(send).toBeDisabled() // unchanged
    fireEvent.keyDown(box, { key: 'Enter' })
    fireEvent.change(box, { target: { value: '   ' } })
    expect(send).toBeDisabled() // empty
    fireEvent.change(box, { target: { value: 'What is my limit?  ' } })
    expect(send).toBeDisabled() // same text, only whitespace differs
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(props.onEdit).not.toHaveBeenCalled()
  })

  it('is disabled while an answer is in flight', () => {
    setup(exchange(), { controlsDisabled: true })
    expect(editButtons().every((b) => b.hasAttribute('disabled'))).toBe(true)
  })

  it('does not ask for confirmation when nothing raised a request', () => {
    const { props } = setup(exchange())
    fireEvent.click(editButtons()[0]!)
    fireEvent.change(screen.getByRole('textbox', { name: 'Edit your message' }), {
      target: { value: 'Something else' },
    })
    fireEvent.keyDown(screen.getByRole('textbox', { name: 'Edit your message' }), { key: 'Enter' })
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(props.onEdit).toHaveBeenCalledOnce()
  })
})

describe('replaying an answer', () => {
  it('is offered on the latest answer only', () => {
    setup(exchange())
    expect(screen.getAllByRole('button', { name: 'Replay answer' })).toHaveLength(1)
    const articles = screen.getAllByRole('article')
    expect(within(articles[0]!).queryByRole('button', { name: 'Replay answer' })).toBeNull()
    expect(within(articles[1]!).getByRole('button', { name: 'Replay answer' })).toBeInTheDocument()
  })

  it('re-asks the customer message the latest answer responded to', () => {
    const { props } = setup(exchange())
    fireEvent.click(screen.getByRole('button', { name: 'Replay answer' }))
    expect(props.onReplay).toHaveBeenCalledWith(2)
  })

  it('is also offered after a failed answer, and not while one is streaming', () => {
    const failed: AgentTurn = { id: 'a2', role: 'agent', status: 'error', steps: [], error: 'boom' }
    const { unmount } = setup([
      { id: 'c1', role: 'customer', text: 'Q' },
      failed,
    ])
    expect(screen.getByRole('button', { name: 'Replay answer' })).toBeInTheDocument()
    unmount()
    setup([
      { id: 'c1', role: 'customer', text: 'Q' },
      { id: 'a1', role: 'agent', status: 'streaming', steps: [] },
    ])
    expect(screen.queryByRole('button', { name: 'Replay answer' })).not.toBeInTheDocument()
  })

  it('is disabled while busy', () => {
    setup(exchange(), { controlsDisabled: true })
    expect(screen.getByRole('button', { name: 'Replay answer' })).toBeDisabled()
  })
})

describe('the guard before discarding a raised request', () => {
  it('asks before replaying an answer that raised a request, and sends nothing if kept', () => {
    const { props } = setup(exchange(true))
    fireEvent.click(screen.getByRole('button', { name: 'Replay answer' }))
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveTextContent(
      'This will discard answers below, including request SR-1A2B3C4D that was already raised, and a new request may be raised.',
    )
    expect(screen.getByRole('button', { name: 'Replay and continue' })).toHaveFocus()
    expect(props.onReplay).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Keep it as it is' }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(props.onReplay).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Replay answer' })).toHaveFocus()
  })

  it('replays once the customer confirms', () => {
    const { props } = setup(exchange(true))
    fireEvent.click(screen.getByRole('button', { name: 'Replay answer' }))
    fireEvent.click(screen.getByRole('button', { name: 'Replay and continue' }))
    expect(props.onReplay).toHaveBeenCalledWith(2)
  })

  it('keeps everything when Escape is pressed in the dialog', () => {
    const { props } = setup(exchange(true))
    fireEvent.click(screen.getByRole('button', { name: 'Replay answer' }))
    fireEvent.keyDown(screen.getByRole('alertdialog'), { key: 'Escape' })
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(props.onReplay).not.toHaveBeenCalled()
  })

  it('asks before an edit that would discard a raised request, and sends nothing if kept', () => {
    const { props } = setup(exchange(true))
    fireEvent.click(editButtons()[1]!)
    const box = screen.getByRole('textbox', { name: 'Edit your message' })
    fireEvent.change(box, { target: { value: 'Someone used my card in Pune' } })
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit and send' })).toHaveFocus()
    expect(props.onEdit).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Keep it as it is' }))
    expect(props.onEdit).not.toHaveBeenCalled()
    expect(screen.queryByRole('textbox', { name: 'Edit your message' })).not.toBeInTheDocument()
  })

  it('sends the edit once confirmed', () => {
    const { props } = setup(exchange(true))
    fireEvent.click(editButtons()[1]!)
    const box = screen.getByRole('textbox', { name: 'Edit your message' })
    fireEvent.change(box, { target: { value: 'Someone used my card in Pune' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send edited message' }))
    fireEvent.click(screen.getByRole('button', { name: 'Edit and send' }))
    expect(props.onEdit).toHaveBeenCalledWith(2, 'Someone used my card in Pune')
  })

  it('names every request an edit of the first message would discard', () => {
    const two = exchange(true, true)
    setup(two)
    fireEvent.click(editButtons()[0]!)
    fireEvent.change(screen.getByRole('textbox', { name: 'Edit your message' }), {
      target: { value: 'changed my mind' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send edited message' }))
    expect(screen.getByRole('alertdialog')).toHaveTextContent(
      'requests SR-1A2B3C4D and SR-1A2B3C4D that were already raised',
    )
  })

  it('only counts requests in what would be discarded, not in what is kept', () => {
    // The first answer raised a request; editing the SECOND message keeps it.
    const { props } = setup(exchange(false, true))
    fireEvent.click(editButtons()[1]!)
    const box = screen.getByRole('textbox', { name: 'Edit your message' })
    fireEvent.change(box, { target: { value: 'another question' } })
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(props.onEdit).toHaveBeenCalledWith(2, 'another question')
  })
})
