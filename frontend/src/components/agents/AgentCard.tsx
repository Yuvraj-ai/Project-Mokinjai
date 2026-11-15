import { useNavigate } from 'react-router-dom'
import { Clock, MessagesSquare, Settings2, Trash2 } from 'lucide-react'
import Badge from '../ui/Badge'
import { cn } from '../../lib/utils'
import type { AgentListItem } from '../../api/agents'

interface AgentCardProps {
  agent: AgentListItem
  llmProfileName?: string
  onClick: () => void
  onDelete: () => void
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return 'Unknown'
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export default function AgentCard({
  agent,
  llmProfileName,
  onClick,
  onDelete,
}: AgentCardProps) {
  const navigate = useNavigate()

  return (
    <div
      onClick={onClick}
      className={cn(
        'relative bg-surface rounded-xl border border-line p-5 h-full flex flex-col',
        'hover:border-line-strong transition-colors duration-150 cursor-pointer group'
      )}
    >
      <div className="flex items-start justify-between mb-2 gap-2">
        <h3 className="text-[15px] font-semibold text-ink truncate leading-snug">
          {agent.name}
        </h3>
        <div
          className="shrink-0 flex items-center gap-0.5"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            title="Chat in Playground"
            aria-label={`Chat with ${agent.name} in Playground`}
            onClick={() => navigate(`/playground?agent=${agent.id}`)}
            className="p-1.5 rounded-md text-ink-subtle hover:text-ink hover:bg-surface-muted opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity duration-150"
          >
            <MessagesSquare className="w-4 h-4" />
          </button>
          <button
            type="button"
            title="Configure"
            aria-label={`Configure ${agent.name}`}
            onClick={onClick}
            className="p-1.5 rounded-md text-ink-subtle hover:text-ink hover:bg-surface-muted opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity duration-150"
          >
            <Settings2 className="w-4 h-4" />
          </button>
          <button
            type="button"
            title="Delete"
            aria-label={`Delete ${agent.name}`}
            onClick={onDelete}
            className="p-1.5 rounded-md text-ink-subtle hover:bg-status-error-soft hover:text-status-error opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity duration-150"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge
          tone={agent.status === 'ready' ? 'success' : 'warning'}
          dot
        >
          {agent.status === 'ready' ? 'Ready' : 'Needs attention'}
        </Badge>
        {llmProfileName && (
          <span className="truncate max-w-[200px] rounded-md border border-line bg-surface-muted px-2 py-0.5 font-mono text-[11px] text-ink-muted">
            {llmProfileName}
          </span>
        )}
      </div>

      {agent.description ? (
        <p className="text-[13px] text-ink-muted line-clamp-2 leading-relaxed mb-4">
          {agent.description}
        </p>
      ) : (
        <p className="text-[13px] text-ink-subtle italic line-clamp-2 leading-relaxed mb-4">
          No description provided
        </p>
      )}

      <div className="flex items-center gap-1.5 text-xs text-ink-subtle mt-auto pt-3 border-t border-line/60 font-mono">
        <Clock className="w-3.5 h-3.5" aria-hidden />
        <span>Modified {formatDate(agent.updated_at)}</span>
      </div>
    </div>
  )
}
