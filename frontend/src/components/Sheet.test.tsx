import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'

import { Sheet } from './Sheet'

function Harness() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open details
      </button>
      <Sheet open={open} side="right" label="Details" onClose={() => setOpen(false)}>
        <h2 tabIndex={-1} data-autofocus>
          Details
        </h2>
        <button type="button">First</button>
        <button type="button" onClick={() => setOpen(false)}>
          Last
        </button>
      </Sheet>
    </>
  )
}

describe('Sheet', () => {
  it('moves focus in on open, traps Tab, and restores focus on Escape', () => {
    render(<Harness />)
    const opener = screen.getByRole('button', { name: 'Open details' })
    opener.focus()
    fireEvent.click(opener)

    const dialog = screen.getByRole('dialog', { name: 'Details' })
    expect(screen.getByRole('heading', { name: 'Details' })).toHaveFocus()

    const last = screen.getByRole('button', { name: 'Last' })
    last.focus()
    fireEvent.keyDown(last, { key: 'Tab' })
    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus()
    fireEvent.keyDown(screen.getByRole('button', { name: 'First' }), { key: 'Tab', shiftKey: true })
    expect(last).toHaveFocus()

    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })

  it('restores focus when closed from inside', () => {
    render(<Harness />)
    const opener = screen.getByRole('button', { name: 'Open details' })
    opener.focus()
    fireEvent.click(opener)
    fireEvent.click(screen.getByRole('button', { name: 'Last' }))
    expect(opener).toHaveFocus()
  })
})
