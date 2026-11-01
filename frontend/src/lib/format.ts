import type { Behaviour, Citation, ReasonCode } from '../api/types'

// Customer-facing outcome titles. `answer` has no decision block.
export const DECISION_TITLE: Record<Exclude<Behaviour, 'answer'>, string> = {
  decline_with_reason: 'Not possible right now',
  refuse: 'I can’t answer this here',
  raise_request: 'Sent to a specialist',
}

// A refusal that still routes the customer is a hand-off, not a dead end.
export const HANDOFF_TITLE = 'A specialist needs to confirm this'

/** Groups for the "How this answer was determined" drawer, in the customer's words. */
export const SOURCE_GROUP: Record<Citation['type'], string> = {
  account: 'Your card account',
  policy: 'Card policy',
  rule: 'Decision rule',
}

export const BEHAVIOUR_LABEL: Record<Behaviour, string> = {
  answer: 'Answered',
  decline_with_reason: 'Declined with reason',
  refuse: 'Refused',
  raise_request: 'Request raised',
}

// Plain-language descriptions from POL-GOV-009 (approved adverse-action reasons).
export const REASON_CODE_LABEL: Record<ReasonCode, string> = {
  AA01: 'Recent missed payments',
  AA02: 'Existing obligations relative to income',
  AA03: 'Limited credit history with us',
  AA04: 'An open dispute on the account',
  AA05: 'A recent change to your limit',
  AA06: 'Information we hold needs to be refreshed',
}

export const QUEUE_LABEL: Record<string, string> = {
  CARDS_URGENT: 'Card block and replacement',
  DISPUTES: 'Disputes',
  SELFSERVE: 'Statements and certificates',
  CREDIT_OPS: 'Credit team',
  PAYMENTS: 'Payments',
  COMPLAINTS: 'Complaints',
  GENERAL: 'Customer service',
}

const words = (s: string) => s.replace(/_/g, ' ').toLowerCase()
const sentence = (s: string) => s.replace(/^\w/, (c) => c.toUpperCase())

export function citationLabel(c: Citation): string {
  if (c.type === 'account') return `Your account: ${words(c.ref.replace(/^account\./, ''))}`
  if (c.type === 'rule') return `Policy rule: ${words(c.ref.replace(/^rule\./, ''))}`
  const [doc, section] = c.ref.split('#')
  if (!section || section === 'body') return doc ?? c.ref
  return /^\d/.test(section) ? `${doc}, section ${section}` : `${doc}, ${words(section)}`
}

/** "account.card_year_spend" -> "Card year spend"; "rule.limit_cap" -> "Limit cap". */
export function fieldLabel(ref: string): string {
  return sentence(words(ref.replace(/^(account|rule)\./, '')))
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : '')).toUpperCase()
}

export function ruleLabel(ruleId: string): string {
  return sentence(words(ruleId))
}

export function formatSla(hours: number): string {
  if (hours < 8) return `${hours} hours`
  const days = hours / 8
  return `${days} working day${days === 1 ? '' : 's'}`
}

export function formatCost(usd: number): string {
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(3)}`
}
