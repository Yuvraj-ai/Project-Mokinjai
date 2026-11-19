import { memo, useEffect, useRef, useState } from 'react'
import { Bot, Send, Square, StopCircle, User, CircleAlert } from 'lucide-react'
import {
  streamSessionChat,
  type ActivityEvent,
  type PlaygroundMessage,
  type PlaygroundSession,
} from '../../api/playground'
import ActivityCard from './ActivityCard'
import ThinkingCard from './ThinkingCard'

interface ThreadPaneProps {
  workspaceId: string | null
  session: PlaygroundSession | null
  messages: PlaygroundMessage[]
  readOnly: boolean
  onTurnEnded: () => void
}

/** What both a fetched row and a streaming turn render through (spec §8). */
interface RenderedAssistant {
  content: string
  reasoning: string
  events: ActivityEvent[]
  status: 'completed' | 'stopped' | 'failed'
  usage: PlaygroundMessage['usage']
  cost_usd: number | null
}

function fromPersisted(message: PlaygroundMessage): RenderedAssistant {
  return {
    content: message.content,
    reasoning: message.reasoning ?? '',
    events: message.activity ?? [],
    status: message.status ?? 'completed',
    usage: message.usage,
    cost_usd: message.cost_usd,
  }
}

/**
 * One card per tool call, not two: the start and end events share a run id,
 * so the end event (result/error + duration) replaces its start ("Calling…")
 * and a start with no end yet stays live. Files-staged events pass through.
 */
function collapseEvents(events: ActivityEvent[]): ActivityEvent[] {
  const ended = new Set(
    events.filter((event) => event.type === 'tool_end').map((event) => event.id)
  )
  return events.filter(
    (event) => event.type !== 'tool_start' || !ended.has(event.id)
  )
}

const AssistantTurn = memo(function AssistantTurn({
  turn,
  streaming,
}: {
  turn: RenderedAssistant
  streaming: boolean
}) {
  const events = collapseEvents(turn.events)
  return (
    <div className="flex max-w-[85%] flex-col">
      {turn.reasoning && <ThinkingCard reasoning={turn.reasoning} live={streaming && !turn.content} />}
      {events.map((event, index) => (
        <ActivityCard key={`${event.type}-${event.id ?? index}`} event={event} />
      ))}
      {turn.content ? (
        <p className="whitespace-pre-wrap px-1 py-1 text-[13px] text-ink">{turn.content}</p>
      ) : streaming ? (
        <p className="px-1 py-1 text-[13px] text-ink-subtle">…</p>
      ) : null}
      {turn.status === 'stopped' && (
        <span className="mx-1 flex items-center gap-1 text-[10.5px] text-ink-subtle">
          <StopCircle className="h-3 w-3" aria-hidden /> stopped
        </span>
      )}
      {turn.status === 'failed' && (
        <span className="mx-1 flex items-center gap-1 text-[10.5px] text-status-error">
          <CircleAlert className="h-3 w-3" aria-hidden /> failed
        </span>
      )}
      {!streaming && turn.usage && turn.usage.total_tokens ? (
        <p className="mx-1 font-mono text-[10.5px] text-ink-subtle">
          {turn.usage.total_tokens} tokens
          {turn.cost_usd != null ? ` · $${turn.cost_usd.toFixed(6)}` : ''}
        </p>
      ) : null}
    </div>
  )
})

/**
 * A persisted turn never changes while a new one streams, so it is memoised on
 * the stable message row. Without this, every token re-rendered the entire
 * history, including every activity card.
 */
const PersistedTurn = memo(function PersistedTurn({ message }: { message: PlaygroundMessage }) {
  return <AssistantTurn turn={fromPersisted(message)} streaming={false} />
})

export default function ThreadPane({
  workspaceId,
  session,
  messages,
  readOnly,
  onTurnEnded,
}: ThreadPaneProps) {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [inflight, setInflight] = useState<RenderedAssistant | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    // One paint per frame at most: smooth scrolling on every streamed token
    // queues overlapping animations on a long thread.
    const frame = requestAnimationFrame(() => {
      bottomRef.current?.scrollIntoView({ block: 'end' })
    })
    return () => cancelAnimationFrame(frame)
  }, [messages, inflight])

  useEffect(() => () => abortRef.current?.abort(), [])

  // Switching sessions must not inherit the previous thread's in-flight
  // turn, draft or error banner.
  useEffect(() => {
    abortRef.current?.abort()
    setInflight(null)
    setError(null)
    setInput('')
    setSending(false)
  }, [session?.id])

  const send = async () => {
    const content = input.trim()
    if (!content || !workspaceId || !session || sending) return

    setSending(true)
    setError(null)
    setInflight({ content: '', reasoning: '', events: [], status: 'completed', usage: null, cost_usd: null })
    setInput('')

    const controller = new AbortController()
    abortRef.current = controller

    // Coalesce streamed deltas into ~20 renders/second. One setState per token
    // on a long tool-heavy turn is what turns a fast model into a frozen tab.
    let pendingContent = ''
    let pendingReasoning = ''
    let flushTimer: number | null = null
    const flush = () => {
      if (flushTimer !== null) {
        window.clearTimeout(flushTimer)
        flushTimer = null
      }
      if (!pendingContent && !pendingReasoning) return
      const content = pendingContent
      const reasoning = pendingReasoning
      pendingContent = ''
      pendingReasoning = ''
      setInflight((current) =>
        current
          ? {
              ...current,
              content: current.content + content,
              reasoning: current.reasoning + reasoning,
            }
          : current
      )
    }
    const scheduleFlush = () => {
      if (flushTimer === null) flushTimer = window.setTimeout(flush, 50)
    }

    try {
      for await (const event of streamSessionChat(
        workspaceId,
        session.id,
        content,
        controller.signal
      )) {
        if (event.type === 'token') {
          pendingContent += event.delta
          scheduleFlush()
        } else if (event.type === 'reasoning') {
          pendingReasoning += event.delta
          scheduleFlush()
        } else if (event.type === 'activity') {
          flush()
          setInflight((current) =>
            current ? { ...current, events: [...current.events, event.payload] } : current
          )
        } else if (event.type === 'done') {
          flush()
          setInflight((current) =>
            current
              ? { ...current, status: event.status as RenderedAssistant['status'], usage: event.usage, cost_usd: event.cost_usd }
              : current
          )
        } else if (event.type === 'error') {
          flush()
          setError(event.detail)
        }
      }
    } catch (caught) {
      if ((caught as Error).name !== 'AbortError') setError((caught as Error).message)
    } finally {
      flush()
      setSending(false)
      abortRef.current = null
      // Wait for the persisted rows to be refetched before dropping the
      // in-flight copy, so the turn never renders twice.
      await Promise.resolve(onTurnEnded())
      setInflight(null)
    }
  }

  const stop = () => abortRef.current?.abort()

  const totalCost = messages.reduce(
    (sum, message) => sum + (message.cost_usd ?? 0),
    0
  )

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <header className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <h2 className="truncate text-[14px] font-semibold text-ink">
          {session ? session.title : 'No session selected'}
        </h2>
        {totalCost > 0 && (
          <span className="font-mono text-[10.5px] text-ink-subtle">
            session · ${totalCost.toFixed(4)}
          </span>
        )}
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && !inflight && (
          <p className="text-[13px] text-ink-subtle">
            {session ? 'Send a message to start this session.' : 'Pick an agent and a session.'}
          </p>
        )}
        {messages.map((message) =>
          message.role === 'user' ? (
            <div key={message.id} className="flex justify-end gap-2">
              <p className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-surface-muted px-3.5 py-2 text-[13px] text-ink">
                {message.content}
              </p>
              <User className="mt-1 h-4 w-4 shrink-0 text-ink-subtle" aria-hidden />
            </div>
          ) : (
            <div key={message.id} className="flex justify-start gap-2">
              <Bot className="mt-1 h-4 w-4 shrink-0 text-ink-subtle" aria-hidden />
              <PersistedTurn message={message} />
            </div>
          )
        )}
        {inflight && (
          <div className="flex justify-start gap-2">
            <Bot className="mt-1 h-4 w-4 shrink-0 text-ink-subtle" aria-hidden />
            <AssistantTurn turn={inflight} streaming={sending} />
          </div>
        )}
        {error && (
          <p className="rounded-lg bg-status-error-soft px-3 py-2 text-[13px] text-status-error">
            {error}
          </p>
        )}
        <div ref={bottomRef} />
      </div>

      <footer className="border-t border-line p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            rows={2}
            disabled={!session || sending}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void send()
              }
            }}
            placeholder={
              readOnly
                ? 'Viewers can read but not chat.'
                : session
                  ? `Message ${session.title}…`
                  : 'Select a session to chat…'
            }
            className="flex-1 resize-none rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60"
          />
          {sending ? (
            <button
              onClick={stop}
              className="flex items-center gap-1 rounded-lg border border-line px-3 py-2 text-[12.5px] text-ink-muted hover:bg-surface-muted hover:text-ink"
            >
              <Square className="h-3 w-3" aria-hidden /> Stop
            </button>
          ) : (
            <button
              onClick={() => void send()}
              disabled={readOnly || !input.trim() || !session}
              className="flex items-center gap-1 rounded-lg bg-primary px-3 py-2 text-[12.5px] text-primary-fg disabled:opacity-50"
            >
              <Send className="h-3 w-3" aria-hidden /> Send
            </button>
          )}
        </div>
      </footer>
    </div>
  )
}
