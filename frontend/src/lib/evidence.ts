// Links an answer's sentences to the claims that back them (see policyText.ts for passages).
//
// The backend returns the message and its cited claims separately (claims are paraphrases,
// not character offsets), so linking is a word-overlap heuristic. The UI labels highlights
// as the "closest matching passage" rather than claiming an exact quote.
//
// Segments are offset based: `text + gap` of every segment, concatenated, is exactly the
// original message, so markdown structure (lists, blank lines) survives marker placement.

const STOP = new Set(
  'the a an and or of to in on for is are be by with your you we our this that it its as at from can not may any per if has have was were will been than then their there'.split(
    ' ',
  ),
)

export function tokens(text: string): Set<string> {
  const normalised = text.toLowerCase().replace(/(\d),(?=\d)/g, '$1')
  const words = normalised.match(/[a-z]+|\d+(?:\.\d+)?/g) ?? []
  return new Set(words.filter((w) => (w.length > 2 || /\d/.test(w)) && !STOP.has(w)))
}

/** Share of the claim's words that appear in the candidate text. */
export function overlap(claim: Set<string>, candidate: Set<string>): number {
  if (claim.size === 0) return 0
  let hit = 0
  for (const w of claim) if (candidate.has(w)) hit++
  return hit / claim.size
}

export interface Segment {
  text: string // a sentence or list item, without trailing whitespace
  markers: number[] // 1-based claim numbers supported by this sentence
  gap: string // the whitespace that followed it in the message (spaces, newlines)
}

// A sentence ends at ". " before a capital, digit, quote, bracket or emphasis; a line ends at
// any newline. Decimals such as "3.5%" have no whitespace after the dot, so they stay whole.
const BREAK = /(?<=[.!?][*"')\]]*)[ \t]+(?=[A-Z0-9"'(*_])|[ \t]*\n\s*/g

export function splitSegments(message: string): Segment[] {
  const segments: Segment[] = []
  let carry = '' // leading whitespace of the message, kept on the first segment
  const push = (unit: string, sep: string) => {
    const text = unit.trimEnd()
    if (!text.trim()) {
      const last = segments[segments.length - 1]
      if (last) last.gap += unit + sep
      else carry += unit + sep
      return
    }
    segments.push({ text: carry + text, markers: [], gap: unit.slice(text.length) + sep })
    carry = ''
  }
  let last = 0
  for (const m of message.matchAll(BREAK)) {
    push(message.slice(last, m.index), m[0])
    last = m.index + m[0].length
  }
  push(message.slice(last), '')
  return segments
}

export function splitSentences(text: string): string[] {
  return splitSegments(text)
    .map((s) => s.text.trim())
    .filter(Boolean)
}

const SENTENCE_MATCH = 0.5

/** Each claim is attached to at most one sentence: the one it overlaps most. */
export function attachMarkers(message: string, claimTexts: string[]): Segment[] {
  const segments = splitSegments(message)
  const sentenceTokens = segments.map((s) => tokens(s.text))
  claimTexts.forEach((claim, i) => {
    const ct = tokens(claim)
    let best = -1
    let bestScore = SENTENCE_MATCH
    sentenceTokens.forEach((st, j) => {
      const score = overlap(ct, st)
      if (score >= bestScore) {
        best = j
        bestScore = score
      }
    })
    if (best >= 0) segments[best]!.markers.push(i + 1)
  })
  return segments
}
