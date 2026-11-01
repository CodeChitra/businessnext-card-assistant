# Design system: "Secure card desk"

## Brief

- **Product:** a retail bank's card-service assistant (Indian context: lakh amounts, CIBIL, re-KYC).
- **Audiences:**
  1. The cardholder, who needs a direct answer and a safe next step.
  2. The reviewer, who needs to see that the answer is grounded. Reviewer tools live in a separate, clearly marked layer.
- **Feel:** a calm, precise private-banking desk. Borders and tonal contrast instead of shadows. No gradients, glass, sparkles or decorative charts.

## The one memorable thing: the ledger rail

Each assistant turn hangs off a thin teal line with one status marker. The marker's **shape and colour** both encode the outcome, so status never depends on colour alone:

| Marker | Meaning |
|---|---|
| teal ring, pulsing | checking |
| teal dot | answered |
| navy square | a decision (declined with reason) |
| amber ring | under review: a request was raised, degraded or safe fallback |
| grey ring | not answered here |
| red diamond | the message failed |

Numbered markers in the prose open that statement's source in the drawer, and the supporting passage gets a single highlighter wipe.

## Tokens (`src/index.css`)

Tailwind's default palette is disabled (`--color-*: initial`), so only these colours exist.

| Token | Light | Dark | Use |
|---|---|---|---|
| `mist` | `#F4F7F8` | `#0C151E` | app background, composer band |
| `paper` | `#FFFFFF` | `#121D28` | nav, header, panels, drawer |
| `sunk` | `#EDF2F4` | `#192634` | hover, skeletons |
| `line` | `#D8E1E5` | `#273746` | borders and dividers |
| `ink` | `#15202B` | `#E6EDF2` | primary text |
| `muted` | `#5A6A77` | `#9AABB8` | secondary text (AA on every surface) |
| `navy` / `navy-wash` | `#17324D` / `#E9EFF5` | `#B9CDE3` / `#1B2C3E` | brand mark, account avatar, customer messages |
| `teal` / `teal-wash` | `#0B6E69` / `#E3F1EF` | `#55BDB4` / `#12302E` | primary action, verified, rail, focus ring |
| `amber` / `amber-wash` | `#9A6200` / `#FBF1DC` | `#E2B05A` / `#332710` | under review, limited answer |
| `red` / `red-wash` | `#B42318` / `#FDECEA` | `#F08A7E` / `#3A1A17` | errors and non-policy warnings only |
| `highlight` | `#FBE7A1` | `#5A4A14` | evidence highlight only |
| `on-accent` | `#FFFFFF` | `#0C151E` | text on teal |

- **Type:** IBM Plex Sans for the UI (body 16 px / 1.6, answers 17 px / 1.7) and IBM Plex Serif only for quoted policy text. `.figures` gives tabular numerals for amounts, references and dates. Sentence case throughout.
- **Radius by purpose:** `rounded-control` 8 px (buttons, inputs), `rounded-panel` 12 px (case card, drawer wells, lists), `rounded-message` 18 px (customer messages only).
- **Elevation:** a single `shadow-sheet`, on overlay sheets only.
- **Motion:** 150–220 ms, and only to explain a change (a sheet sliding in, the highlighter wipe, the checking pulse). `prefers-reduced-motion` disables all of it.
- **Focus:** a 2 px teal outline. Base styles sit in `@layer base` so utilities can override them.

## Layout

```
≥1280   ┌ Nav 264 ┬ Header (card, secure session, details, theme) ┬ Drawer 360 ┐
        │ brand   │ conversation ≤ 800 px, centred                 │ docked at  │
        │ new     │ ┃ ledger rail + answer                         │ ≥1440,     │
        │ shortcuts│┃ case card / decision panel                   │ overlay    │
        │ testing │                                                │ below      │
        │ account │ [ Ask about your card               (send) ]   │            │
        └─────────┴────────────────────────────────────────────────┴────────────┘
<1280   Nav becomes a left sheet behind the menu button.
<768    Single column; the drawer opens as a full-screen sheet; touch targets ≥ 44 px.
```

The drawer stays **closed until asked for**: through "How this answer was determined", a numbered marker, or the header details button.

## Answer text: markdown, markers and reveal

- **Markdown, safely.** The model writes light markdown (short paragraphs, `-` bullets, `**bold**` for key figures). `AnswerMarkdown` renders only `p, ul, ol, li, strong, em, br, code, blockquote`; headings, tables, links, images and HTML never become elements (their text survives). A bank answer must not be able to send a customer somewhere or load remote content.
- **Typography:** 17 px / 1.7 at a 68 ch measure, blocks spaced by `space-y-3`, bullets by `space-y-2` with visible markers, bold at weight 600. Tokens only.
- **Citation markers live in the markdown source.** `lib/citationMarkers.ts` inserts a private-use sentinel after the sentence or bullet each claim supports; the `p`, `li`, `strong` and `em` renderers swap sentinels for the marker button. `attachMarkers` is offset based (`text + gap` rebuilds the message exactly), so lists and blank lines survive. The old sentence splitter dropped newlines and collapsed bullets into one paragraph.
- **Progressive reveal, not token streaming.** Raw model tokens are never shown: text reaches the customer only after citation validation and the output guards (SPEC §6.2, §14). So an answer that arrives live is revealed word by word on the client (`useReveal`), paced to finish in about 3.5 s however long it is. Honest framing: this is presentation of text that is already validated; the progress steps remain the true streaming signal.
  - History and re-rendered turns never animate (`animate` is set only on a live final).
  - The reveal cuts at word boundaries, never inside a citation sentinel, and closes an open `**` so no stray asterisks flash.
  - The case card, "How this answer was determined" and follow-ups wait until the reveal ends, then fade in (180 ms).
  - `prefers-reduced-motion`: the whole answer appears at once.
  - "Show full answer" (or a click on the text) completes it immediately.

## Scroll model

The page never scrolls. The shell is a fixed-height column (`100dvh`, `body { overflow: hidden }`): header and composer are `shrink-0`, and **one** element scrolls, the conversation.

- The scroller is positioned (`relative` wrapper, `absolute inset-0 overflow-y-auto`), so absolutely positioned descendants, such as the screen-reader copy of an answer, are contained by it. An unpositioned `sr-only` element anchors to the page, stretches its scroll height, and lets wheel scrolling chain out of the conversation and slide the whole app, composer included, off screen. That was a real bug, reproduced and measured before the fix (document `scrollHeight` 4827 vs a 900 px viewport; after wheeling, composer bottom at -2100). `overscroll-behavior: contain` and `overflow-anchor: none` keep it that way.
- **Never `scrollIntoView`.** It scrolls every ancestor, not just the conversation. The scroller moves itself with `scrollTo`.
- **Stick to the bottom** (`useStickToBottom`): the conversation follows new content (a new turn, each reveal tick) only while the reader is within 120 px of the end, or has just sent a message. A reader who scrolled up to re-read is never pulled down; a quiet "Jump to latest" appears instead.
- Two details that matter, both found by measuring rather than guessing. Scroll events arrive a frame late, so when an answer grows taller in between, the echo of the scroller's *own* scroll would be measured against the new height and misread as the reader leaving; the hook recognises its own echo by position (it lands exactly where it scrolled to; a reader's scroll lands elsewhere). And scroll anchoring is off (`overflow-anchor: none`), because the browser nudging `scrollTop` when content changes looks like the reader scrolling away.
- Opening an editor above the end releases the follow, so the editor is not scrolled out of view, and its growth does not raise "Jump to latest".

## Editing and replaying

- **Edit.** Every customer message has an "Edit message" pencil: revealed on hover and focus, always visible on touch (`pointer-coarse`), 44 px on small screens. It opens an inline editor (prefilled, autosized, 2000 characters). Enter sends, Shift+Enter adds a line, Escape or "Cancel" closes it and returns focus to the pencil. "Send edited message" is disabled when the text is empty or unchanged.
- **Replay.** The **latest** answer, finished or failed, offers "Replay answer". It re-asks the same question.
- Both **discard the message and everything after it**, and the server forks its thread at that point. The client sends the current `thread_id` and `rewind_to` = the number of customer messages *before* it that were actually answered (a failed turn never completed on the server, so it is not counted). The reply's `meta.thread_id` is the new thread. With no thread yet, no `rewind_to` is sent.
- Both wait while an answer is on its way or being revealed, and offline. Focus moves to the composer (not on touch devices, to avoid raising the keyboard); "Message updated, getting a new answer" is announced politely.
- **Guard for consequential actions.** If the answers about to be discarded include a service request that was already raised, an inline `alertdialog` asks first: "This will discard answers below, including request SR-XXXX that was already raised, and a new request may be raised." Focus goes to the primary button ("Edit and send" / "Replay and continue"); "Keep it as it is" and Escape change nothing. Only requests in what would be discarded count. Ordinary questions never ask.

## Follow-up questions

Under "How this answer was determined", the **latest** answer shows up to three short questions under a quiet "You might also ask". Choosing one sends it as the customer's next message (an ordinary question: no confirmation). They are hidden while another message is in flight, offline, or when the backend returned none. Buttons are at least 44 px tall and wrap at 320 px.

## Components

`NavPanel`, `AccountSwitcher`, `ConversationHeader`, `Conversation` (with `AssistantTurn`, new-conversation and choose-cardholder states), `AgentAnswer`, `AnswerMarkdown`, `SupportCaseCard`, `EvidenceDrawer`, `Sheet` (+ `useDialog` focus trap/restore), `MessageComposer`, `EditableMessage`, `ReplayAnswer`, `DiscardConfirm`, `Inspector` ("Developer details"), `PolicyText`, `icons`.

## Customer vs developer layer

- The customer sees plain-language outcomes, reasons and source groups ("Your card account", "Card policy", "Decision rule").
- **Testing tools** (collapsed, dashed border) hold the demo scenarios, simulated faults and the **Developer details** switch.
- With developer details on, each answer shows a dashed panel with the pipeline, rules fired, model, tokens, cost, latency, prompts and trace. Reason codes and policy IDs also appear.
- A case card appears only when the backend returned a `service_request`. The UI never invents a reference.

## Writing

- Sentence case. No all-caps labels, no middle-dot meta strings.
- Name a concrete next step ("Try sending again", "Copy"). Avoid "Submit" or "Continue".
- Failure copy says what happened and what to do, never how the pipeline works.
- The composer reminds the customer not to share their full card number, PIN or CVV.

## Accessibility floor

- WCAG 2.2 AA contrast for all text tokens in both themes (checked).
- Landmarks: `nav`, `main`, the drawer as `aside` (docked) or a modal `dialog` (overlay); the conversation is a `log`.
- Overlay sheets trap focus, close on Escape and the scrim, and return focus to whatever opened them.
- Live regions announce progress, limited answers, errors and the copied reference. Focus never moves when a message arrives.
- While an answer is revealing, the visible text is `aria-hidden` and the full text sits in an `sr-only` copy, so screen readers hear the answer once, not in fragments. Markers are plain (non-focusable) badges until the reveal ends, so nothing focusable ever lives inside `aria-hidden`.
- Edit and replay: the editor is a labelled textbox, Escape cancels, focus returns to where it came from; the discard confirmation is an `alertdialog` with focus on its primary action; the new answer is announced once through a polite live region.
- Icon-only buttons have accessible names.
