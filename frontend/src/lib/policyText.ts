// Turns a policy chunk's markdown-ish text into blocks for display, and finds the unit
// (table row, list item or sentence) that best supports a claim.

import { overlap, splitSentences, tokens } from './evidence'

export type Block =
  | { kind: 'table'; header: string[]; rows: string[][] }
  | { kind: 'list'; items: string[] }
  | { kind: 'para'; sentences: string[] }

export interface UnitRef {
  block: number
  unit: number // row / item / sentence index within the block
}

const cells = (line: string) =>
  line
    .trim()
    .replace(/^\||\|$/g, '')
    .split('|')
    .map((c) => c.trim())

/** Source files are hard-wrapped; paragraphs and list items are reflowed. */
export function parsePolicy(text: string): Block[] {
  const blocks: Block[] = []
  const lines = text.split('\n')
  let i = 0
  while (i < lines.length) {
    const line = lines[i]!.trim()
    if (!line) {
      i++
      continue
    }
    if (line.startsWith('|')) {
      const tableLines: string[] = []
      while (i < lines.length && lines[i]!.trim().startsWith('|')) tableLines.push(lines[i++]!.trim())
      const [head, ...rest] = tableLines.filter((l) => !/^\|[\s|:-]+\|$/.test(l))
      blocks.push({ kind: 'table', header: cells(head ?? ''), rows: rest.map(cells) })
      continue
    }
    if (/^[-*] /.test(line)) {
      const items: string[] = []
      while (i < lines.length && lines[i]!.trim()) {
        const l = lines[i]!.trim()
        if (/^[-*] /.test(l)) items.push(l.slice(2))
        else if (items.length) items[items.length - 1] += ` ${l}`
        i++
      }
      blocks.push({ kind: 'list', items })
      continue
    }
    const para: string[] = []
    while (i < lines.length && lines[i]!.trim() && !/^([-*] |\|)/.test(lines[i]!.trim()))
      para.push(lines[i++]!.trim())
    blocks.push({ kind: 'para', sentences: splitSentences(para.join(' ')) })
  }
  return blocks
}

const UNIT_MATCH = 0.25

export function bestUnit(blocks: Block[], claim: string): UnitRef | null {
  const ct = tokens(claim)
  let best: UnitRef | null = null
  let bestScore = UNIT_MATCH
  blocks.forEach((b, bi) => {
    const units =
      b.kind === 'table' ? b.rows.map((r) => r.join(' ')) : b.kind === 'list' ? b.items : b.sentences
    units.forEach((u, ui) => {
      const score = overlap(ct, tokens(u))
      if (score > bestScore) {
        best = { block: bi, unit: ui }
        bestScore = score
      }
    })
  })
  return best
}
