import { useState } from 'react'
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import type { PlaygroundSession } from '../../api/playground'
import { cn } from '../../lib/utils'

interface SessionPaneProps {
  agentName: string
  sessions: PlaygroundSession[]
  selectedId: string | null
  busy: boolean
  onSelect: (sessionId: string) => void
  onCreate: () => void
  onRename: (sessionId: string, title: string) => void
  onDelete: (sessionId: string) => void
}

function relativeTime(iso: string): string {
  const delta = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(delta / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

/** Pane 2 (spec P5): the selected agent's sessions, newest first. */
export default function SessionPane({
  agentName,
  sessions,
  selectedId,
  busy,
  onSelect,
  onCreate,
  onRename,
  onDelete,
}: SessionPaneProps) {
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [confirming, setConfirming] = useState<string | null>(null)

  const commitRename = () => {
    if (editing) {
      const title = draft.trim()
      if (title) onRename(editing, title)
    }
    setEditing(null)
  }

  return (
    <div className="flex h-full w-[240px] shrink-0 flex-col border-r border-line">
      <div className="flex items-center justify-between px-3 pt-3 pb-2">
        <p className="min-w-0 truncate text-[10px] font-semibold uppercase tracking-wider text-ink-subtle">
          {agentName}
        </p>
        <button
          onClick={onCreate}
          disabled={busy}
          title="New session"
          className="flex h-6 w-6 items-center justify-center rounded-md text-ink-muted hover:bg-surface-muted hover:text-ink disabled:opacity-50"
        >
          <Plus className="h-4 w-4" aria-hidden />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto pb-3">
        {sessions.length === 0 && (
          <p className="px-3 text-[12px] text-ink-subtle">
            New session to start chatting.
          </p>
        )}
        {sessions.map((session) => (
          <div
            key={session.id}
            className={cn(
              'group mx-1.5 mb-0.5 flex items-center gap-1 rounded-md px-2 py-1.5',
              session.id === selectedId ? 'bg-surface-muted' : 'hover:bg-surface-muted'
            )}
          >
            {editing === session.id ? (
              <>
                <input
                  autoFocus
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') commitRename()
                    if (event.key === 'Escape') setEditing(null)
                  }}
                  className="min-w-0 flex-1 rounded border border-line bg-surface px-1.5 py-0.5 text-[12px] text-ink focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <button
                  onClick={commitRename}
                  className="text-status-success"
                  title="Save title"
                >
                  <Check className="h-3.5 w-3.5" aria-hidden />
                </button>
                <button onClick={() => setEditing(null)} className="text-ink-subtle" title="Cancel">
                  <X className="h-3.5 w-3.5" aria-hidden />
                </button>
              </>
            ) : confirming === session.id ? (
              <>
                <button
                  onClick={() => {
                    onDelete(session.id)
                    setConfirming(null)
                  }}
                  className="flex-1 truncate text-left text-[12px] text-status-error"
                >
                  Delete for good?
                </button>
                <button onClick={() => setConfirming(null)} className="text-ink-subtle" title="Cancel">
                  <X className="h-3.5 w-3.5" aria-hidden />
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => onSelect(session.id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <span className="block truncate text-[12.5px] text-ink">{session.title}</span>
                  <span className="block text-[10.5px] text-ink-subtle">
                    {relativeTime(session.updated_at)}
                  </span>
                </button>
                <span className="hidden shrink-0 items-center gap-0.5 group-hover:flex">
                  <button
                    onClick={() => {
                      setEditing(session.id)
                      setDraft(session.title)
                    }}
                    className="text-ink-subtle hover:text-ink"
                    title="Rename"
                  >
                    <Pencil className="h-3 w-3" aria-hidden />
                  </button>
                  <button
                    onClick={() => setConfirming(session.id)}
                    className="text-ink-subtle hover:text-status-error"
                    title="Delete session"
                  >
                    <Trash2 className="h-3 w-3" aria-hidden />
                  </button>
                </span>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
