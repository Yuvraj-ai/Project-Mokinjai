import { User } from 'lucide-react'
import type { PlaygroundMessage, PlaygroundSession } from '../../api/playground'

interface ThreadPaneProps {
  session: PlaygroundSession | null
  messages: PlaygroundMessage[]
}

/**
 * Pane 3 (spec P5): the thread. Task 5 renders fetched turns as plain text
 * bubbles; Task 6 adds the streaming lifecycle and the activity/thinking
 * cards that both live turns and replays render through.
 */
export default function ThreadPane({ session, messages }: ThreadPaneProps) {
  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <header className="border-b border-line px-4 py-2.5">
        <h2 className="truncate text-[14px] font-semibold text-ink">
          {session ? session.title : 'No session selected'}
        </h2>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <p className="text-[13px] text-ink-subtle">
            {session ? 'Send a message to start this session.' : 'Pick an agent and a session.'}
          </p>
        )}
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex gap-2 ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {message.role === 'user' ? (
              <p className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-surface-muted px-3.5 py-2 text-[13px] text-ink">
                {message.content}
              </p>
            ) : (
              <p className="max-w-[80%] whitespace-pre-wrap px-1 py-1 text-[13px] text-ink">
                {message.content}
              </p>
            )}
            {message.role === 'user' && (
              <User className="mt-1 h-4 w-4 shrink-0 text-ink-subtle" aria-hidden />
            )}
          </div>
        ))}
      </div>

      <footer className="border-t border-line p-3">
        <textarea
          rows={2}
          disabled
          placeholder="Select a session to chat…"
          className="w-full resize-none rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-ink placeholder:text-ink-subtle focus:outline-none"
        />
      </footer>
    </div>
  )
}
