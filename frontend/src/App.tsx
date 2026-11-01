import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from './api/client'
import type { CustomerSummary, Health, Simulate } from './api/types'
import { Conversation, type Selection } from './components/Conversation'
import { ConversationHeader } from './components/ConversationHeader'
import { EvidenceDrawer } from './components/EvidenceDrawer'
import { MessageComposer } from './components/MessageComposer'
import { NavPanel } from './components/NavPanel'
import { Sheet } from './components/Sheet'
import { useChat } from './hooks/useChat'
import { useStickToBottom } from './hooks/useStickToBottom'
import { useMediaQuery, useOnline } from './hooks/useMediaQuery'
import { useInspector, useTheme } from './hooks/usePreferences'

export default function App() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [customerId, setCustomerId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [simulate, setSimulate] = useState<Simulate | null>(null)
  // A statement the user picked; otherwise the drawer follows the newest answer.
  const [pinned, setPinned] = useState<Selection | null>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [navOpen, setNavOpen] = useState(false)
  // Spoken once when an edit or replay starts; cleared when its answer is in.
  const [announcement, setAnnouncement] = useState('')
  const composer = useRef<HTMLTextAreaElement>(null)
  const chat = useChat(customerId)
  const { ref: scrollRef, onScroll, follow, stick, release, jumpToLatest, away } = useStickToBottom()
  const theme = useTheme()
  const inspector = useInspector()
  const online = useOnline()
  const navDocked = useMediaQuery('(min-width: 1280px)')
  const drawerDocked = useMediaQuery('(min-width: 1440px)')

  const fetchSession = useCallback(() => {
    Promise.all([api.customers(), api.health()])
      .then(([c, h]) => {
        setCustomers(c)
        setHealth(h)
        setLoadError(false)
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }, [])
  useEffect(fetchSession, [fetchSession])
  const retryLoad = () => {
    setLoading(true)
    fetchSession()
  }

  const latest = [...chat.turns].reverse().find((t) => t.role === 'agent' && t.response)
  const selection: Selection | null = pinned ?? (latest ? { turnId: latest.id, claim: null } : null)

  const focusComposer = () =>
    // After any sheet has closed and handed focus back.
    window.setTimeout(() => {
      const el = composer.current
      el?.focus()
      el?.setSelectionRange(el.value.length, el.value.length)
    }, 0)

  const switchCustomer = (id: string) => {
    setNavOpen(false)
    if (id === customerId) return
    chat.reset()
    setPinned(null)
    setDetailsOpen(false)
    setCustomerId(id)
  }

  const newConversation = () => {
    chat.reset()
    setPinned(null)
    setDetailsOpen(false)
    setDraft('')
    setNavOpen(false)
    focusComposer()
  }

  const suggest = (question: string) => {
    setDraft(question)
    setNavOpen(false)
    focusComposer()
  }

  const send = () => {
    setAnnouncement('')
    stick()
    void chat.send(draft, simulate)
    setPinned(null) // the drawer moves on to the new answer
    setDraft('')
    setSimulate(null) // simulated failures apply to one message only
  }

  // A suggested follow-up is an ordinary question: it is sent as-is, with no simulated fault.
  const followUp = (question: string) => {
    setAnnouncement('')
    stick()
    void chat.send(question)
    setPinned(null)
  }

  // Edit and replay both re-ask from a customer message: the server forks its thread at that
  // point, and the client drops that message and everything after it.
  const redo = (turnIndex: number, text: string, spoken: string) => {
    setPinned(null) // the drawer must not point at a discarded answer
    setAnnouncement(spoken)
    stick()
    void chat.rewind(turnIndex, text)
    // Keep the keyboard user's place without popping the on-screen keyboard on touch devices.
    if (!window.matchMedia?.('(pointer: coarse)').matches) focusComposer()
  }
  const edit = (turnIndex: number, text: string) =>
    redo(turnIndex, text, 'Message updated, getting a new answer')
  const replay = (turnIndex: number) => {
    const turn = chat.turns[turnIndex]
    if (turn?.role === 'customer') redo(turnIndex, turn.text, 'Replaying your question, getting a new answer')
  }
  const select = (s: Selection) => {
    // Selecting the open statement again collapses it.
    setPinned(
      selection && selection.turnId === s.turnId && selection.claim === s.claim && s.claim !== null
        ? { ...s, claim: null }
        : s,
    )
    setDetailsOpen(true)
  }

  const current = customers.find((c) => c.customer_id === customerId) ?? null
  const drawerTurn = chat.turns.find((t) => t.id === selection?.turnId)
  const drawerResponse = drawerTurn?.role === 'agent' ? (drawerTurn.response ?? null) : null

  const nav = (
    <NavPanel
      customers={customers}
      current={current}
      onCustomer={switchCustomer}
      onNewConversation={newConversation}
      onSuggest={suggest}
      onScenario={(cid, q) => {
        switchCustomer(cid)
        suggest(q)
      }}
      health={health}
      simulate={simulate}
      onSimulate={setSimulate}
      inspector={inspector.on}
      onInspector={inspector.toggle}
      onClose={navDocked ? undefined : () => setNavOpen(false)}
    />
  )

  return (
    <div className="flex h-full overflow-hidden bg-mist">
      {navDocked ? (
        <div className="h-full w-[264px] shrink-0 border-r border-line">{nav}</div>
      ) : (
        <Sheet open={navOpen} side="left" label="Menu" onClose={() => setNavOpen(false)} className="w-[min(88vw,300px)]">
          {nav}
        </Sheet>
      )}

      <main className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <ConversationHeader
          current={current}
          showMenu={!navDocked}
          onMenu={() => setNavOpen(true)}
          detailsOpen={detailsOpen}
          detailsAvailable={Boolean(latest)}
          onDetails={() => setDetailsOpen((v) => !v)}
          theme={theme.theme}
          onTheme={theme.toggle}
        />

        {loadError && (
          <div role="alert" className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-red-wash px-4 py-2.5 text-sm sm:px-6">
            <p className="min-w-0 flex-1">
              <span className="font-medium text-red">Card Assistant isn’t reachable right now.</span>{' '}
              <span className="text-ink">Check your connection, or start the API on port 8000, then try again.</span>
            </p>
            <button
              type="button"
              onClick={retryLoad}
              className="min-h-9 rounded-control border border-line bg-paper px-3 font-medium text-teal hover:border-teal"
            >
              Try again
            </button>
          </div>
        )}
        {!online && (
          <p role="status" className="border-b border-line bg-amber-wash px-4 py-2 text-sm text-ink sm:px-6">
            <span className="font-medium text-amber">You’re offline.</span> Reconnect to send a
            message; your conversation is still here.
          </p>
        )}

        {/* The only scroller. It is positioned, so absolutely positioned descendants (the
            screen-reader copies of answers) are contained by it instead of stretching the page.
            Scroll anchoring is off: the browser nudging scrollTop when content changes would look
            like the reader scrolling away, and stop us following (seen at phone widths). */}
        <div className="relative min-h-0 flex-1">
          <div
            ref={scrollRef}
            onScroll={onScroll}
            className="absolute inset-0 overflow-y-auto overscroll-contain [overflow-anchor:none]"
          >
            <Conversation
              turns={chat.turns}
              customer={current}
              customers={customers}
              customersLoading={loading}
              inspector={inspector.on}
              selection={selection}
              onSelect={select}
              onSuggest={suggest}
              onRetry={(q) => {
                stick()
                void chat.send(q)
              }}
              onFollowUp={followUp}
              followUpsDisabled={chat.busy || !online}
              onChooseCustomer={switchCustomer}
              onGrow={follow}
              onEdit={edit}
              onEditStart={release}
              onReplay={replay}
              controlsDisabled={chat.busy || !online}
            />
          </div>
          <p role="status" aria-live="polite" className="sr-only">
            {chat.busy ? announcement : ''}
          </p>
          {away && (
            <button
              type="button"
              onClick={jumpToLatest}
              className="absolute bottom-3 left-1/2 min-h-11 -translate-x-1/2 rounded-control border border-line bg-paper px-4 text-sm font-medium text-teal shadow-sheet hover:border-teal"
            >
              Jump to latest
            </button>
          )}
        </div>

        <MessageComposer
          inputRef={composer}
          value={draft}
          onChange={setDraft}
          onSend={send}
          disabled={!customerId || chat.busy || !online}
          placeholder={current ? 'Ask about your card' : 'Choose a demo cardholder to start'}
        />
      </main>

      <Sheet
        open={detailsOpen}
        side="right"
        label="How this answer was determined"
        onClose={() => setDetailsOpen(false)}
        docked={drawerDocked}
        className={drawerDocked ? 'w-[360px] shrink-0' : 'w-full md:w-[380px]'}
      >
        <EvidenceDrawer
          key={selection?.turnId ?? 'none'}
          response={drawerResponse}
          selectedClaim={selection?.claim ?? null}
          onSelectClaim={(n) => selection && select({ turnId: selection.turnId, claim: n })}
          onClose={() => setDetailsOpen(false)}
          devDetails={inspector.on}
        />
      </Sheet>
    </div>
  )
}
