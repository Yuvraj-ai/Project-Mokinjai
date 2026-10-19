import { useEffect, useRef, useState } from 'react'
import { Bot, Loader2, Send, Square, User } from 'lucide-react'
import { streamAgentChat, type ChatMessage } from '../../api/agents'

interface AgentChatPanelProps {
  workspaceId: string
  agentId: string
  agentName: string
  onClose: () => void
}

/**
 * The test surface for a saved agent (D-1). History lives in this component and
 * is sent with every turn; each turn records one `Execution` with
 * `trigger_type="chat"`.
 */
export default function AgentChatPanel({
  workspaceId,
  agentId,
  agentName,
  onClose,
}: AgentChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [activity, setActivity] = useState<string | null>(null)
  const [summary, setSummary] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activity])

  useEffect(() => () => abortRef.current?.abort(), [])

  const send = async () => {
    const text = input.trim()
    if (!text || busy) return

    // A failed turn leaves an empty assistant bubble; it must not become history.
    const history: ChatMessage[] = [
      ...messages.filter((message) => message.content.length > 0),
      { role: 'user', content: text },
    ]
    setMessages([...history, { role: 'assistant', content: '' }])
    setInput('')
    setBusy(true)
    setError(null)
    setSummary(null)
    setActivity(null)

    const controller = new AbortController()
    abortRef.current = controller
    try {
      for await (const event of streamAgentChat(workspaceId, agentId, history, controller.signal)) {
        if (event.type === 'token') {
          setMessages((previous) => {
            const next = [...previous]
            const last = next[next.length - 1]
            next[next.length - 1] = { role: 'assistant', content: `${last.content}${event.delta}` }
            return next
          })
        } else if (event.type === 'tool') {
          setActivity(event.status === 'running' ? `Calling ${event.name}…` : null)
        } else if (event.type === 'done') {
          setActivity(null)
          setSummary(
            `${event.usage.output_tokens ?? 0} output tokens · $${event.cost_usd.toFixed(6)}`
          )
        } else if (event.type === 'error') {
          setActivity(null)
          setError(event.detail)
        }
      }
    } catch (caught) {
      if ((caught as Error).name !== 'AbortError') setError((caught as Error).message)
    } finally {
      setMessages((previous) => {
        const last = previous[previous.length - 1]
        return last?.role === 'assistant' && last.content.length === 0
          ? previous.slice(0, -1)
          : previous
      })
      setBusy(false)
      abortRef.current = null
    }
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-ink-100/60 dark:border-ink-700/60 px-4 py-2.5">
        <div className="min-w-0">
          <h2 className="truncate font-display text-lg text-ink-800 dark:text-cream-100">
            {agentName}
          </h2>
          <p className="text-[10px] text-ink-400">Chat test — each turn is recorded as a run.</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg px-2 py-1 text-xs text-ink-500 hover:bg-ink-50 dark:hover:bg-ink-700"
        >
          Close
        </button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <p className="text-xs text-ink-400">Send a message to try this agent.</p>
        )}
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex gap-2 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {message.role === 'assistant' && (
              <Bot className="mt-1 h-3.5 w-3.5 shrink-0 text-ink-300" />
            )}
            <p
              className={`max-w-[80%] whitespace-pre-wrap rounded-xl px-3 py-2 text-xs ${
                message.role === 'user'
                  ? 'bg-accent-warm/10 text-ink-800 dark:text-cream-100'
                  : 'bg-cream-100 dark:bg-ink-700/60 text-ink-700 dark:text-cream-100'
              }`}
            >
              {message.content || (busy ? '…' : '')}
            </p>
            {message.role === 'user' && <User className="mt-1 h-3.5 w-3.5 shrink-0 text-ink-300" />}
          </div>
        ))}
        {activity && (
          <p className="flex items-center gap-2 text-[10px] text-ink-400">
            <Loader2 className="h-3 w-3 animate-spin" /> {activity}
          </p>
        )}
        {error && (
          <p className="rounded-lg border border-status-error/40 px-3 py-2 text-[11px] text-status-error">
            {error}
          </p>
        )}
        {summary && <p className="text-[10px] text-ink-400">{summary}</p>}
        <div ref={bottomRef} />
      </div>

      <footer className="border-t border-ink-100/60 dark:border-ink-700/60 p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            rows={2}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void send()
              }
            }}
            placeholder="Ask the agent something…"
            className="flex-1 resize-none rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-xs text-ink-800 dark:text-cream-100"
          />
          {busy ? (
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              className="flex items-center gap-1 rounded-lg border border-ink-100 dark:border-ink-600 px-3 py-2 text-xs text-ink-600 dark:text-cream-100"
            >
              <Square className="h-3 w-3" /> Stop
            </button>
          ) : (
            <button
              type="button"
              disabled={!input.trim()}
              onClick={() => void send()}
              className="flex items-center gap-1 rounded-lg bg-accent-warm px-3 py-2 text-xs text-white disabled:opacity-50"
            >
              <Send className="h-3 w-3" /> Send
            </button>
          )}
        </div>
      </footer>
    </div>
  )
}
