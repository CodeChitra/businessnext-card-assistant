// Customer shortcuts. Each one is a question the corpus and account tools can answer.
export interface Suggestion {
  label: string
  question: string
}

export const SUGGESTIONS: Suggestion[] = [
  { label: 'Check my credit limit', question: 'What is my current credit limit?' },
  { label: 'Ask about a limit increase', question: 'Can I get a higher credit limit?' },
  { label: 'Was my annual fee waived?', question: 'My annual fee was charged, I thought it was waived. Can you check?' },
  { label: 'Report a payment I don’t recognise', question: 'There is a payment on my card that I don’t recognise.' },
]
