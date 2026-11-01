import { attachMarkers } from './evidence'

// Private-use characters never occur in customer text, so a marker can ride inside the
// markdown source and be swapped for a button when the text node is rendered.
export const OPEN = ''
export const CLOSE = ''
const SENTINEL = new RegExp(`${OPEN}([\\d,]+)${CLOSE}`)

/** The message with citation sentinels inserted after the sentence each claim supports. */
export function markSource(message: string, claimTexts: string[]): string {
  return attachMarkers(message, claimTexts)
    .map((s) => s.text + (s.markers.length ? `${OPEN}${s.markers.join(',')}${CLOSE}` : '') + s.gap)
    .join('')
}

/** Splits text into plain strings and claim-number groups, e.g. "a<1,2>b" -> ["a", [1,2], "b"]. */
export function splitMarkers(text: string): (string | number[])[] {
  const parts = text.split(new RegExp(SENTINEL.source, 'g'))
  // split() with one capture group alternates text, capture, text, ...
  return parts
    .map((part, i) => (i % 2 === 1 ? part.split(',').map(Number) : part))
    .filter((p) => p !== '')
}

/** Plain text of a marked source: no sentinels, no markdown syntax (for screen readers). */
export function plainText(marked: string): string {
  return marked
    .replace(new RegExp(SENTINEL.source, 'g'), '')
    .replace(/\*\*/g, '')
    .replace(/^[ \t]*[-*][ \t]+/gm, '')
}
