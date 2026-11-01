import { act, renderHook } from '@testing-library/react'

import { OPEN, CLOSE } from '../lib/citationMarkers'
import { MAX_MS, TICK_MS } from '../lib/reveal'
import { useReveal } from './useReveal'

const source = `The annual fee applies.${OPEN}1${CLOSE} Your card-year spend is below the waiver threshold, so the fee was charged. `.repeat(
  3,
)

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('useReveal', () => {
  it('reveals progressively, then completes with the exact source', () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useReveal(source, true))
    expect(result.current.done).toBe(false)
    expect(result.current.text).toBe('')

    act(() => void vi.advanceTimersByTime(TICK_MS * 10))
    const partial = result.current.text
    expect(partial.length).toBeGreaterThan(0)
    expect(partial.length).toBeLessThan(source.length)
    expect(result.current.done).toBe(false)

    act(() => void vi.advanceTimersByTime(MAX_MS + 500))
    expect(result.current.done).toBe(true)
    expect(result.current.text).toBe(source)
  })

  it('takes about as long as planned, not a fraction of it', () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useReveal(source, true))
    act(() => void vi.advanceTimersByTime(1000))
    expect(result.current.done).toBe(false) // word-finishing must not rush the reveal
    act(() => void vi.advanceTimersByTime(MAX_MS))
    expect(result.current.done).toBe(true)
  })

  it('never exposes half of a citation marker mid-reveal', () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useReveal(source, true))
    for (let i = 0; i < 400 && !result.current.done; i++) {
      act(() => void vi.advanceTimersByTime(TICK_MS))
      const t = result.current.text
      expect(t.split(OPEN).length).toBe(t.split(CLOSE).length)
    }
    expect(result.current.done).toBe(true)
  })

  it('skip completes immediately', () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useReveal(source, true))
    act(() => result.current.skip())
    expect(result.current.done).toBe(true)
    expect(result.current.text).toBe(source)
  })

  it('shows history turns (animate off) instantly', () => {
    const { result } = renderHook(() => useReveal(source, false))
    expect(result.current.done).toBe(true)
    expect(result.current.text).toBe(source)
  })

  it('shows everything at once for people who prefer reduced motion', () => {
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: q.includes('prefers-reduced-motion'),
      addEventListener: () => {},
      removeEventListener: () => {},
    }))
    const { result } = renderHook(() => useReveal(source, true))
    expect(result.current.done).toBe(true)
    expect(result.current.text).toBe(source)
  })
})
