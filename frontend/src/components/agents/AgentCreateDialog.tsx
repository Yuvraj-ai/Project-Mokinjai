import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { AGENT_DESCRIPTION_MAX, AGENT_NAME_MAX } from '../../api/agents'

interface AgentCreateDialogProps {
  onContinue: (name: string, description: string) => void
  onClose: () => void
}

/** Step one: the name and description the directive asks for before the config opens. */
export default function AgentCreateDialog({ onContinue, onClose }: AgentCreateDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const valid = name.trim().length > 0

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink-900/30 p-4">
      <div className="w-full max-w-md rounded-xl border border-ink-100/60 dark:border-ink-700/60 bg-white dark:bg-ink-800 p-5 shadow-xl">
        <h2 className="mb-1 font-display text-xl text-ink-800 dark:text-cream-100">New agent</h2>
        <p className="mb-4 text-[11px] text-ink-400">
          Name it, then configure its model and capabilities.
        </p>

        <label className="mb-3 block">
          <span className="mb-1 block text-[10px] uppercase tracking-wider font-semibold text-ink-400">
            Name
          </span>
          <input
            autoFocus
            value={name}
            maxLength={AGENT_NAME_MAX}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && valid) onContinue(name.trim(), description.trim())
            }}
            placeholder="Support agent"
            className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-sm text-ink-800 dark:text-cream-100"
          />
        </label>

        <label className="mb-4 block">
          <span className="mb-1 block text-[10px] uppercase tracking-wider font-semibold text-ink-400">
            Description
          </span>
          <input
            value={description}
            maxLength={AGENT_DESCRIPTION_MAX}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Answers customer questions from the handbook."
            className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-sm text-ink-800 dark:text-cream-100"
          />
        </label>

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-xs text-ink-500 hover:bg-ink-50 dark:hover:bg-ink-700"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!valid}
            onClick={() => onContinue(name.trim(), description.trim())}
            className="flex items-center gap-1 rounded-lg bg-accent-warm px-3 py-1.5 text-xs text-white disabled:opacity-50"
          >
            <Plus className="h-3 w-3" /> Continue
          </button>
        </div>
      </div>
    </div>
  )
}
