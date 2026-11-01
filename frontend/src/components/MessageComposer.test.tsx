import { fireEvent, render, screen } from '@testing-library/react'

import { MessageComposer } from './MessageComposer'

function setup(value: string, disabled = false) {
  const onSend = vi.fn()
  render(
    <MessageComposer value={value} onChange={() => {}} onSend={onSend} disabled={disabled} placeholder="Ask about your card" />,
  )
  return { onSend, box: screen.getByRole('textbox', { name: 'Message' }) }
}

describe('MessageComposer', () => {
  it('sends on Enter', () => {
    const { onSend, box } = setup('What is my limit?')
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(onSend).toHaveBeenCalledOnce()
  })

  it('keeps Shift+Enter for a new line', () => {
    const { onSend, box } = setup('Line one')
    fireEvent.keyDown(box, { key: 'Enter', shiftKey: true })
    expect(onSend).not.toHaveBeenCalled()
  })

  it('disables sending an empty message', () => {
    const { onSend, box } = setup('   ')
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(onSend).not.toHaveBeenCalled()
  })

  it('does not send while disabled', () => {
    const { onSend, box } = setup('Hello', true)
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(onSend).not.toHaveBeenCalled()
  })

  it('reminds the customer not to share card secrets', () => {
    setup('')
    expect(screen.getByText(/Don’t share your full card number, PIN or CVV/)).toBeInTheDocument()
  })
})
