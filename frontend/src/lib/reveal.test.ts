import { CLOSE, OPEN, markSource, plainText, splitMarkers } from './citationMarkers'
import { MAX_MS, MIN_MS, TICK_MS, closeOpenEmphasis, durationFor, revealCut, ticksFor } from './reveal'

describe('durationFor', () => {
  it('keeps every answer between 2.5 and 3.5 seconds', () => {
    expect(durationFor(10)).toBe(MIN_MS)
    expect(durationFor(150)).toBe(3000)
    expect(durationFor(50_000)).toBe(MAX_MS)
    expect(ticksFor(420) * TICK_MS).toBeGreaterThanOrEqual(MIN_MS)
    expect(ticksFor(420) * TICK_MS).toBeLessThanOrEqual(MAX_MS + TICK_MS)
  })
})

describe('revealCut', () => {
  const source = `First sentence.${OPEN}1,2${CLOSE} Second one.`

  it('finishes the current word instead of stopping mid-word', () => {
    const text = 'The limit is 120000 today'
    expect(text.slice(0, revealCut(text, 6))).toBe('The limit')
  })

  it('never stops inside a citation sentinel, wherever the budget lands', () => {
    for (let at = 0; at <= source.length + 2; at++) {
      const shown = source.slice(0, revealCut(source, at))
      expect(shown.split(OPEN).length).toBe(shown.split(CLOSE).length) // open/close balanced
    }
  })

  it('never stops on a bare bullet, which would flash an empty list item', () => {
    const text = 'Intro:\n\n- First item here.\n- Second item here.'
    for (let at = 0; at <= text.length; at++) {
      const shown = text.slice(0, revealCut(text, at))
      expect(shown).not.toMatch(/(^|\n)[ \t]*-[ \t]*$/)
    }
  })

  it('always shows something and stops at the end', () => {
    expect(revealCut('abc', 0)).toBeGreaterThan(0)
    expect(revealCut('abc', 50)).toBe(3)
  })
})

describe('closeOpenEmphasis', () => {
  it('closes a half-revealed bold span', () => {
    expect(closeOpenEmphasis('- **Eligibility chec')).toBe('- **Eligibility chec**')
    expect(closeOpenEmphasis('**done** and more')).toBe('**done** and more')
  })
})

describe('citation markers in the markdown source', () => {
  it('inserts a sentinel after the supported sentence, keeping the list structure', () => {
    const marked = markSource('Intro:\n\n- Fee waived at 4,00,000 spend.\n- Other point.', [
      'Fee waived on spend of 4,00,000',
    ])
    expect(marked).toBe(`Intro:\n\n- Fee waived at 4,00,000 spend.${OPEN}1${CLOSE}\n- Other point.`)
  })

  it('splits sentinels back out and strips them for screen readers', () => {
    expect(splitMarkers(`a${OPEN}1,2${CLOSE}b`)).toEqual(['a', [1, 2], 'b'])
    expect(plainText(`- **Bold:** text.${OPEN}1${CLOSE}\n- Next`)).toBe('Bold: text.\nNext')
  })
})
