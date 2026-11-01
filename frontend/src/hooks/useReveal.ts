import { useCallback, useEffect, useState } from 'react'

import { TICK_MS, closeOpenEmphasis, revealCut, ticksFor } from '../lib/reveal'

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

/**
 * Progressively reveals text that has ALREADY passed citation validation. The model's raw
 * tokens are never shown (SPEC: text reaches the customer only after validation), so this
 * is presentation, not transport. Off, or with reduced motion, the text is complete at once.
 */
export function useReveal(source: string, enabled: boolean) {
  const [pos, setPos] = useState(() => (enabled && !prefersReducedMotion() ? 0 : source.length))
  const length = source.length
  const done = pos >= length

  useEffect(() => {
    if (done) return
    const total = ticksFor(length)
    let tick = 0
    const id = window.setInterval(() => {
      tick++
      const next = tick >= total ? length : revealCut(source, Math.ceil((length * tick) / total))
      setPos((p) => Math.max(p, next)) // never moves backwards
    }, TICK_MS)
    return () => window.clearInterval(id)
  }, [done, source, length])

  const skip = useCallback(() => setPos(length), [length])
  return { text: done ? source : closeOpenEmphasis(source.slice(0, pos)), done, skip }
}
