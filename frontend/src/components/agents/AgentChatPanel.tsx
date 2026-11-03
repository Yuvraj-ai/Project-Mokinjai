import { useEffect, useRef, useState } from 'react'
import { Bot, Loader2, Send, Square, User } from 'lucide-react'
import { streamAgentChat, type ChatMessage } from '../../api/agents'
import Button from '../ui/Button'
import { cn } from '../../lib/utils'

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
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h2 className="truncate text-[15px] font-semibold text-ink">{agentName}</h2>
          <p className="text-xs text-ink-subtle">Chat test — each turn is recorded as a run.</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <p className="text-[13px] text-ink-subtle">Send a message to try this agent.</p>
        )}
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex gap-2 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {message.role === 'assistant' && (
              <Bot className="mt-1 h-4 w-4 shrink-0 text-ink-subtle" aria-hidden />
            )}
            {message.role === 'user' ? (
              <p className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-surface-muted px-3.5 py-2 text-[13px] text-ink">
                {message.content || (busy ? '…' : '')}
              </p>
            ) : (
              <p className="max-w-[80%] whitespace-pre-wrap px-1 py-1 text-[13px] text-ink">
                {message.content || (busy ? '…' : '')}
              </p>
            )}
            {message.role === 'user' && <User className="mt-1 h-4 w-4 shrink-0 text-ink-subtle" aria-hidden />}
          </div>
        ))}
        {activity && (
          <p className="flex items-center gap-2 text-xs text-ink-subtle">
            <Loader2 className="h-3 w-3 animate-spin" /> {activity}
          </p>
        )}
        {error && (
          <p className="rounded-lg bg-status-error-soft px-3 py-2 text-[13px] text-status-error">
            {error}
          </p>
        )}
        {summary && <p className="font-mono text-[11px] text-ink-subtle">{summary}</p>}
        <div ref={bottomRef} />
      </div>

      <footer className="border-t border-line p-3">
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
            className="flex-1 resize-none rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
          />
          {busy ? (
            <Button variant="secondary" size="sm" onClick={() => abortRef.current?.abort()}>
              <Square className="h-3 w-3" aria-hidden /> Stop
            </Button>
          ) : (
            <Button size="sm" disabled={!input.trim()} onClick={() => void send()}>
              <Send className="h-3 w-3" aria-hidden /> Send
            </Button>
          )}
        </div>
      </footer>
    </div>
  )
}
