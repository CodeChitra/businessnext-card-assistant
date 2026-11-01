import { CLOSE, OPEN } from './citationMarkers'

export const TICK_MS = 16
export const MIN_MS = 2500
export const MAX_MS = 3500

/** Any answer takes 2.5-3.5 s: long ones are capped, short ones aren't crawled out. */
export function durationFor(length: number): number {
  return Math.min(MAX_MS, Math.max(MIN_MS, length * 20))
}

export function ticksFor(length: number): number {
  return Math.ceil(durationFor(length) / TICK_MS)
}

/**
 * Where to cut after revealing `at` characters: finishes the current word and never stops
 * inside a citation sentinel (a half-shown marker would flash as stray glyphs). Driven by an
 * absolute budget, so word-finishing can't make the reveal run faster than planned.
 */
export function revealCut(source: string, at: number): number {
  let cut = Math.min(source.length, Math.max(1, at))
  while (cut < source.length && !/\s/.test(source[cut]!)) cut++
  // Don't stop on a bare bullet ("- "): it would flash an empty list item.
  const lineStart = source.lastIndexOf('\n', cut - 1) + 1
  if (/^[ \t]*[-*][ \t]*$/.test(source.slice(lineStart, cut))) {
    while (cut < source.length && /\s/.test(source[cut]!)) cut++
    while (cut < source.length && !/\s/.test(source[cut]!)) cut++
  }
  const open = source.lastIndexOf(OPEN, cut - 1)
  if (open !== -1 && open > source.lastIndexOf(CLOSE, cut - 1)) {
    const close = source.indexOf(CLOSE, cut)
    cut = close === -1 ? source.length : close + 1
  }
  return cut
}

/** A cut can land inside **bold**; close it so the text doesn't flash literal asterisks. */
export function closeOpenEmphasis(partial: string): string {
  return (partial.match(/\*\*/g)?.length ?? 0) % 2 === 1 ? `${partial}**` : partial
}
