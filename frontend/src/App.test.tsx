import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import App from './App'
import { api } from './api/client'
import type { AgentResponse, Health } from './api/types'

vi.mock('./api/client', () => ({
  api: { customers: vi.fn(), health: vi.fn(), policyChunk: vi.fn(), streamChat: vi.fn() },
}))
const mocked = vi.mocked(api)

const health: Health = {
  status: 'ok',
  as_of_date: '2026-09-01',
  chunks_indexed: 40,
  models: { primary: 'fake' },
  prompt_versions: {},
  tracing: { enabled: false, project: null, reason: '' },
  demo_faults: false,
}

const answer: AgentResponse = {
  behaviour: 'answer',
  message: 'Your credit limit is 1,20,000.',
  claims: [{ text: 'Your credit limit is 1,20,000', citations: [{ type: 'account', ref: 'account.current_limit' }] }],
  reason_codes: [],
  service_request: null,
  degraded: false,
  follow_ups: [],
  meta: {
    model: 'fake',
    prompt_versions: {},
    input_tokens: 1,
    output_tokens: 1,
    cost_usd: 0,
    latency_ms: 10,
    trace_id: null,
    thread_id: 't1',
    fallback_used: false,
    repaired: false,
    safe_fallback: false,
    retrieval_miss: false,
    rules_fired: [],
  },
}

beforeEach(() => {
  vi.resetAllMocks()
  mocked.customers.mockResolvedValue([{ customer_id: 'CUST-2000', name: 'Priya Kapoor', card_product: 'Signature' }])
  mocked.health.mockResolvedValue(health)
})

async function signIn() {
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: /Priya Kapoor/ }))
  return screen.getByRole('textbox', { name: 'Message' })
}

describe('App', () => {
  it('sends a message for the signed-in cardholder and shows the answer', async () => {
    mocked.streamChat.mockResolvedValue(answer)
    const box = await signIn()
    fireEvent.change(box, { target: { value: 'What is my limit?' } })
    fireEvent.keyDown(box, { key: 'Enter' })

    expect(await screen.findByText('Your credit limit is 1,20,000.', { exact: false })).toBeInTheDocument()
    expect(mocked.streamChat).toHaveBeenCalledWith(
      expect.objectContaining({ customer_id: 'CUST-2000', message: 'What is my limit?' }),
      expect.any(Function),
      expect.any(AbortSignal),
    )
    expect(box).toHaveValue('')
  })

  it('opens the evidence drawer with focus inside, and returns focus on Escape', async () => {
    mocked.streamChat.mockResolvedValue(answer)
    const box = await signIn()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument() // closed until asked for
    fireEvent.change(box, { target: { value: 'What is my limit?' } })
    fireEvent.keyDown(box, { key: 'Enter' })

    fireEvent.click(await screen.findByRole('button', { name: 'Show full answer' }))
    const link = await screen.findByRole('button', { name: /How this answer was determined \(1 source\)/ })
    link.focus()
    fireEvent.click(link)
    const drawer = screen.getByRole('dialog', { name: 'How this answer was determined' })
    expect(screen.getByRole('heading', { name: 'How this answer was determined' })).toHaveFocus()
    expect(drawer).toHaveTextContent('Your credit limit is 1,20,000')

    fireEvent.keyDown(drawer, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(link).toHaveFocus()
  })

  it('opens a single statement’s source from its marker', async () => {
    mocked.streamChat.mockResolvedValue(answer)
    const box = await signIn()
    fireEvent.change(box, { target: { value: 'Limit?' } })
    fireEvent.keyDown(box, { key: 'Enter' })
    fireEvent.click(await screen.findByRole('button', { name: 'Show full answer' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Show source 1' }))
    expect(screen.getByRole('button', { name: /Your credit limit is 1,20,000/, expanded: true })).toBeInTheDocument()
    expect(screen.getByText('Your card account')).toBeInTheDocument()
    expect(screen.getByText('Current limit')).toBeInTheDocument()
  })

  it('lets the customer retry a failed answer', async () => {
    mocked.streamChat.mockRejectedValueOnce(new Error('The account service timed out.')).mockResolvedValueOnce(answer)
    const box = await signIn()
    fireEvent.change(box, { target: { value: 'What is my limit?' } })
    fireEvent.keyDown(box, { key: 'Enter' })

    fireEvent.click(await screen.findByRole('button', { name: 'Try sending again' }))
    expect(await screen.findByText('Your credit limit is 1,20,000.', { exact: false })).toBeInTheDocument()
    expect(mocked.streamChat).toHaveBeenCalledTimes(2)
    expect(mocked.streamChat.mock.calls[1]![0].message).toBe('What is my limit?')
  })

  it('recovers when the service was unreachable on load', async () => {
    mocked.customers.mockRejectedValueOnce(new Error('down'))
    render(<App />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('isn’t reachable')
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('button', { name: /Priya Kapoor/ })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('reaches the menu, shortcuts and new conversation from the keyboard', async () => {
    mocked.streamChat.mockResolvedValue(answer)
    await signIn()
    const menu = screen.getByRole('button', { name: 'Open menu' })
    menu.focus()
    fireEvent.click(menu)
    const sheet = screen.getByRole('dialog', { name: 'Menu' })
    fireEvent.click(screen.getAllByRole('button', { name: 'Check my credit limit' })[0]!)
    expect(screen.queryByRole('dialog', { name: 'Menu' })).not.toBeInTheDocument()
    expect(sheet).not.toBeInTheDocument()
    const box = screen.getByRole('textbox', { name: 'Message' })
    expect(box).toHaveValue('What is my current credit limit?')
    await waitFor(() => expect(box).toHaveFocus())
  })

  it('sends a suggested follow-up as the next message, with no simulated fault', async () => {
    mocked.streamChat
      .mockResolvedValueOnce({ ...answer, follow_ups: ['What documents do I need?'] })
      .mockResolvedValueOnce(answer)
    const box = await signIn()
    fireEvent.change(box, { target: { value: 'Can I get a higher limit?' } })
    fireEvent.keyDown(box, { key: 'Enter' })

    // The answer reveals progressively; skip so the extras appear without waiting.
    fireEvent.click(await screen.findByRole('button', { name: 'Show full answer' }))
    fireEvent.click(await screen.findByRole('button', { name: 'What documents do I need?' }))

    await waitFor(() => expect(mocked.streamChat).toHaveBeenCalledTimes(2))
    expect(mocked.streamChat.mock.calls[1]![0]).toMatchObject({
      customer_id: 'CUST-2000',
      message: 'What documents do I need?',
      simulate: null,
    })
    expect(await screen.findAllByText('What documents do I need?')).not.toHaveLength(0) // shown as the customer's message
  })

  describe('edit and replay', () => {
    const reply = (thread: string, over: Partial<AgentResponse> = {}): AgentResponse => ({
      ...answer,
      ...over,
      meta: { ...answer.meta, thread_id: thread },
    })

    // Send a message and let its answer finish revealing (edit and replay wait for that).
    async function ask(box: HTMLElement, text: string) {
      fireEvent.change(box, { target: { value: text } })
      fireEvent.keyDown(box, { key: 'Enter' })
      fireEvent.click(await screen.findByRole('button', { name: 'Show full answer' }))
      await screen.findByRole('button', { name: 'Replay answer' })
    }
    const request = (n: number) => mocked.streamChat.mock.calls[n]![0]

    it('an edit forks the thread at the right point and discards what came after', async () => {
      mocked.streamChat
        .mockResolvedValueOnce(reply('t1'))
        .mockResolvedValueOnce(reply('t2'))
        .mockResolvedValueOnce(reply('t3'))
      const box = await signIn()
      await ask(box, 'First question')
      await ask(box, 'Second question')
      expect(request(0)).not.toHaveProperty('rewind_to') // an ordinary send is unchanged
      expect(request(1)).toMatchObject({ thread_id: 't1' })
      expect(request(1)).not.toHaveProperty('rewind_to')

      fireEvent.click(screen.getAllByRole('button', { name: 'Edit message' })[1]!)
      const editor = screen.getByRole('textbox', { name: 'Edit your message' })
      fireEvent.change(editor, { target: { value: 'Second question, reworded' } })
      fireEvent.keyDown(editor, { key: 'Enter' })

      await waitFor(() => expect(mocked.streamChat).toHaveBeenCalledTimes(3))
      expect(request(2)).toMatchObject({
        customer_id: 'CUST-2000',
        message: 'Second question, reworded',
        thread_id: 't2', // continues the current thread; the server forks it
        rewind_to: 1, // one completed customer turn is kept
      })
      expect(await screen.findByText('Second question, reworded')).toBeInTheDocument()
      expect(screen.queryByText('Second question')).not.toBeInTheDocument()
      expect(screen.getByText('First question')).toBeInTheDocument()
    })

    it('editing the first message rewinds to nothing and drops every later turn', async () => {
      mocked.streamChat
        .mockResolvedValueOnce(reply('t1'))
        .mockResolvedValueOnce(reply('t2'))
        .mockResolvedValueOnce(reply('t3'))
      const box = await signIn()
      await ask(box, 'First question')
      await ask(box, 'Second question')

      fireEvent.click(screen.getAllByRole('button', { name: 'Edit message' })[0]!)
      const editor = screen.getByRole('textbox', { name: 'Edit your message' })
      fireEvent.change(editor, { target: { value: 'A different first question' } })
      fireEvent.click(screen.getByRole('button', { name: 'Send edited message' }))

      await waitFor(() => expect(mocked.streamChat).toHaveBeenCalledTimes(3))
      expect(request(2)).toMatchObject({ thread_id: 't2', rewind_to: 0 })
      expect(screen.queryByText('Second question')).not.toBeInTheDocument()
      expect(screen.queryByText('First question')).not.toBeInTheDocument()
    })

    it('replay re-sends the same text with the same rewind point', async () => {
      mocked.streamChat
        .mockResolvedValueOnce(reply('t1'))
        .mockResolvedValueOnce(reply('t2'))
        .mockResolvedValueOnce(reply('t3'))
      const box = await signIn()
      await ask(box, 'First question')
      await ask(box, 'Second question')

      fireEvent.click(screen.getByRole('button', { name: 'Replay answer' }))
      await waitFor(() => expect(mocked.streamChat).toHaveBeenCalledTimes(3))
      expect(request(2)).toMatchObject({
        message: 'Second question',
        thread_id: 't2',
        rewind_to: 1,
        simulate: null,
      })
      // Still exactly one "Second question": the old pair was replaced, not duplicated.
      expect(screen.getAllByText('Second question')).toHaveLength(1)
    })

    it('counts only completed turns when rewinding past a failed one', async () => {
      mocked.streamChat
        .mockResolvedValueOnce(reply('t1'))
        .mockRejectedValueOnce(new Error('timed out'))
        .mockResolvedValueOnce(reply('t1b'))
        .mockResolvedValueOnce(reply('t2'))
      const box = await signIn()
      await ask(box, 'Answered')
      fireEvent.change(box, { target: { value: 'Failed' } })
      fireEvent.keyDown(box, { key: 'Enter' })
      await screen.findByRole('alert')
      fireEvent.change(box, { target: { value: 'Answered again' } })
      fireEvent.keyDown(box, { key: 'Enter' })
      fireEvent.click(await screen.findByRole('button', { name: 'Show full answer' }))
      await screen.findByRole('button', { name: 'Replay answer' })

      // Three customer turns sit on screen, but the failed one never completed on the server,
      // so editing the last message rewinds to 1 completed turn, not 2.
      fireEvent.click(screen.getAllByRole('button', { name: 'Edit message' })[2]!)
      const editor = screen.getByRole('textbox', { name: 'Edit your message' })
      fireEvent.change(editor, { target: { value: 'Answered, edited' } })
      fireEvent.keyDown(editor, { key: 'Enter' })
      await waitFor(() => expect(mocked.streamChat).toHaveBeenCalledTimes(4))
      expect(request(3)).toMatchObject({ thread_id: 't1b', rewind_to: 1 })
    })

    it('does not send rewind_to when no thread exists yet', async () => {
      mocked.streamChat.mockRejectedValueOnce(new Error('timed out')).mockResolvedValueOnce(reply('t1'))
      const box = await signIn()
      fireEvent.change(box, { target: { value: 'Will fail' } })
      fireEvent.keyDown(box, { key: 'Enter' })
      await screen.findByRole('alert')

      fireEvent.click(screen.getByRole('button', { name: 'Replay answer' }))
      await waitFor(() => expect(mocked.streamChat).toHaveBeenCalledTimes(2))
      expect(request(1)).toMatchObject({ message: 'Will fail', thread_id: null })
      expect(request(1)).not.toHaveProperty('rewind_to')
    })

    it('asks before discarding a request that was already raised, and sends nothing if kept', async () => {
      const raised = reply('t1', {
        behaviour: 'raise_request',
        service_request: { request_id: 'SR-1A2B3C4D', queue: 'DISPUTES', sla_hours: 16 },
      })
      mocked.streamChat.mockResolvedValueOnce(raised).mockResolvedValueOnce(reply('t2'))
      const box = await signIn()
      await ask(box, 'Someone used my card')

      fireEvent.click(screen.getByRole('button', { name: 'Replay answer' }))
      expect(screen.getByRole('alertdialog')).toHaveTextContent('request SR-1A2B3C4D that was already raised')
      fireEvent.click(screen.getByRole('button', { name: 'Keep it as it is' }))
      expect(mocked.streamChat).toHaveBeenCalledTimes(1)

      fireEvent.click(screen.getByRole('button', { name: 'Replay answer' }))
      fireEvent.click(screen.getByRole('button', { name: 'Replay and continue' }))
      await waitFor(() => expect(mocked.streamChat).toHaveBeenCalledTimes(2))
      expect(request(1)).toMatchObject({ message: 'Someone used my card', thread_id: 't1', rewind_to: 0 })
    })

    it('is disabled while an answer is on its way', async () => {
      let finish: (r: AgentResponse) => void = () => {}
      mocked.streamChat
        .mockResolvedValueOnce(reply('t1'))
        .mockImplementationOnce(() => new Promise<AgentResponse>((resolve) => (finish = resolve)))
      const box = await signIn()
      await ask(box, 'First question')
      fireEvent.change(box, { target: { value: 'Second question' } })
      fireEvent.keyDown(box, { key: 'Enter' })

      await waitFor(() => expect(screen.getAllByRole('button', { name: 'Edit message' })[0]).toBeDisabled())
      expect(screen.queryByRole('button', { name: 'Replay answer' })).not.toBeInTheDocument()
      finish(reply('t2'))
      fireEvent.click(await screen.findByRole('button', { name: 'Show full answer' }))
      await waitFor(() => expect(screen.getAllByRole('button', { name: 'Edit message' })[0]).toBeEnabled())
    })

    it('announces the new answer to screen readers, and moves focus to the composer', async () => {
      let finish: (r: AgentResponse) => void = () => {}
      mocked.streamChat
        .mockResolvedValueOnce(reply('t1'))
        .mockImplementationOnce(() => new Promise<AgentResponse>((resolve) => (finish = resolve)))
      const box = await signIn()
      await ask(box, 'First question')
      fireEvent.click(screen.getByRole('button', { name: 'Edit message' }))
      const editor = screen.getByRole('textbox', { name: 'Edit your message' })
      fireEvent.change(editor, { target: { value: 'Reworded' } })
      fireEvent.keyDown(editor, { key: 'Enter' })

      expect(await screen.findByText('Message updated, getting a new answer')).toBeInTheDocument()
      await waitFor(() => expect(box).toHaveFocus())
      finish(reply('t2'))
      await waitFor(() =>
        expect(screen.queryByText('Message updated, getting a new answer')).not.toBeInTheDocument(),
      )
    })
  })

  describe('scrolling', () => {
    it('follows new messages by scrolling its own container, never with scrollIntoView', async () => {
      const intoView = vi.fn()
      const scrollTo = vi.fn()
      const originalInto = Element.prototype.scrollIntoView
      const originalTo = Element.prototype.scrollTo
      Element.prototype.scrollIntoView = intoView
      Element.prototype.scrollTo = scrollTo as never
      try {
        mocked.streamChat.mockResolvedValue(answer)
        const box = await signIn()
        fireEvent.change(box, { target: { value: 'What is my limit?' } })
        fireEvent.keyDown(box, { key: 'Enter' })
        await screen.findByRole('button', { name: 'Show full answer' })
        expect(scrollTo).toHaveBeenCalled()
        expect(intoView).not.toHaveBeenCalled()
        // The scroller is the log's parent: the one element that scrolls.
        expect(scrollTo.mock.contexts.every((c) => c === screen.getByRole('log').parentElement)).toBe(true)
      } finally {
        Element.prototype.scrollIntoView = originalInto
        Element.prototype.scrollTo = originalTo
      }
    })

    it('keeps the composer outside the scrolling area', async () => {
      mocked.streamChat.mockResolvedValue(answer)
      const box = await signIn()
      const scroller = document.querySelector('[role=log]')
      expect(scroller).toBeNull() // empty conversation: nothing to scroll yet
      fireEvent.change(box, { target: { value: 'Hello' } })
      fireEvent.keyDown(box, { key: 'Enter' })
      await screen.findByRole('log')
      expect(screen.getByRole('log').parentElement).not.toContainElement(box)
    })
  })
})
