import { useCallback, useEffect, useState } from 'react'
import { KeyRound, Plus, Settings2 } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { listWorkspaces } from '../api/workspaces'
import {
  listApiKeys,
  type ApiKeyRow,
  type ApiKeyCreated,
  createApiKey,
} from '../api/apiKeys'
import { cn } from '../lib/utils'

const EXPIRATION_OPTIONS = [
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: '1 year', days: 365 },
  { label: 'Never expires', days: null },
]

const RESET_OPTIONS = [
  { label: 'N/A (lifetime total)', value: null },
  { label: 'Daily', value: 'daily' },
  { label: 'Weekly', value: 'weekly' },
  { label: 'Monthly', value: 'monthly' },
]

export function StatusChip({ status }: { status: ApiKeyRow['status'] }) {
  const styles: Record<ApiKeyRow['status'], string> = {
    active: 'bg-status-success-soft text-status-success',
    disabled: 'bg-surface-muted text-ink-muted',
    expired: 'bg-surface-muted text-ink-subtle line-through',
    revoked: 'bg-status-error-soft text-status-error',
  }
  return (
    <span className={cn('rounded-full px-2 py-0.5 text-[10.5px] font-medium', styles[status])}>
      {status[0].toUpperCase() + status.slice(1)}
    </span>
  )
}

function relative(iso: string | null): string {
  if (!iso) return 'Never'
  const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function NewKeyDialog({
  workspaceId,
  onClose,
  onCreated,
}: {
  workspaceId: string
  onClose: () => void
  onCreated: (created: ApiKeyCreated) => void
}) {
  const [name, setName] = useState('')
  const [expirationDays, setExpirationDays] = useState<number | null>(90)
  const [creditLimit, setCreditLimit] = useState('')
  const [resetPeriod, setResetPeriod] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const create = async () => {
    if (!name.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      const created = await createApiKey(workspaceId, {
        name: name.trim(),
        expires_at:
          expirationDays != null
            ? new Date(Date.now() + expirationDays * 86_400_000).toISOString()
            : null,
        credit_limit_usd: creditLimit.trim() || null,
        credit_reset_period: (creditLimit.trim() ? resetPeriod : null) as never,
      })
      onCreated(created)
    } catch {
      setError('Could not create the key.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl border border-line bg-surface p-6">
        <div className="mb-4 flex items-start justify-between">
          <h2 className="text-[15px] font-semibold text-ink">New API key</h2>
          <button onClick={onClose} className="text-ink-subtle hover:text-ink" aria-label="Close">
            ×
          </button>
        </div>
        {error && <p className="mb-3 text-[12.5px] text-status-error">{error}</p>}

        <label className="mb-1 block text-[12.5px] font-medium text-ink">Name *</label>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder='e.g. "Chatbot Key"'
          className="mb-4 w-full rounded-lg border border-line bg-surface-muted px-3 py-2 text-[13px] text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
        />

        <label className="mb-1 block text-[12.5px] font-medium text-ink">Expiration *</label>
        <select
          value={expirationDays ?? 'never'}
          onChange={(event) =>
            setExpirationDays(event.target.value === 'never' ? null : Number(event.target.value))
          }
          className="mb-4 w-full rounded-lg border border-line bg-surface-muted px-3 py-2 text-[13px] text-ink focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {EXPIRATION_OPTIONS.map((option) => (
            <option key={option.label} value={option.days ?? 'never'}>
              {option.label}
            </option>
          ))}
        </select>

        <div className="mb-4 rounded-lg border border-line p-3">
          <p className="mb-2 text-[12.5px] font-medium text-ink">Key limit</p>
          <label className="mb-1 block text-[11.5px] text-ink-muted">Credit limit ($)</label>
          <input
            value={creditLimit}
            onChange={(event) => setCreditLimit(event.target.value)}
            placeholder="Leave blank for unlimited"
            inputMode="decimal"
            className="mb-2 w-full rounded-lg border border-line bg-surface-muted px-3 py-2 text-[13px] text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <label className="mb-1 block text-[11.5px] text-ink-muted">Reset limit every…</label>
          <select
            value={resetPeriod ?? ''}
            onChange={(event) => setResetPeriod(event.target.value || null)}
            disabled={!creditLimit.trim()}
            className="w-full rounded-lg border border-line bg-surface-muted px-3 py-2 text-[13px] text-ink focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          >
            {RESET_OPTIONS.map((option) => (
              <option key={option.label} value={option.value ?? ''}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex justify-end">
          <button
            onClick={() => void create()}
            disabled={!name.trim() || busy}
            className="rounded-lg bg-primary px-4 py-2 text-[13px] font-medium text-primary-fg disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  )
}

export function PlaintextModal({ created, onClose }: { created: ApiKeyCreated; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const snippet = `curl -X POST ${window.location.origin}/v1/chat \\
  -H "Authorization: Bearer ${created.key}" \\
  -H "Content-Type: application/json" \\
  -d '{"agent_id": "<agent-id>", "message": "Hello!"}'`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-xl border border-line bg-surface p-6">
        <h2 className="text-[15px] font-semibold text-ink">Save your key now</h2>
        <p className="mt-1 text-[12.5px] text-ink-muted">
          This is the only time the full key is shown. Store it somewhere safe —
          it cannot be recovered, only rotated.
        </p>
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-line bg-surface-muted px-3 py-2">
          <code className="min-w-0 flex-1 truncate font-mono text-[12.5px] text-ink">{created.key}</code>
          <button
            onClick={() => {
              void navigator.clipboard.writeText(created.key)
              setCopied(true)
            }}
            className="rounded-md border border-line px-2 py-1 text-[11.5px] text-ink-muted hover:text-ink"
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
        <p className="mt-4 mb-1 text-[12.5px] font-medium text-ink">Quickstart</p>
        <pre className="overflow-auto rounded-lg border border-line bg-surface-muted p-3 font-mono text-[11px] text-ink-muted">
{snippet}
        </pre>
        <div className="mt-4 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-lg bg-primary px-4 py-2 text-[13px] font-medium text-primary-fg"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ApiKeysPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [keys, setKeys] = useState<ApiKeyRow[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [plaintext, setPlaintext] = useState<ApiKeyCreated | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    listWorkspaces().then((workspaces) => {
      if (workspaces.length > 0) setWorkspaceId(workspaces[0].id)
    })
  }, [])

  const refresh = useCallback(() => {
    if (!workspaceId) return
    listApiKeys(workspaceId)
      .then(setKeys)
      .finally(() => setLoading(false))
  }, [workspaceId])

  useEffect(refresh, [refresh])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-[13px] text-ink-subtle">
        Loading…
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-8">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-ink">API keys</h1>
            <p className="mt-1 text-sm text-ink-muted">Create and manage your API keys.</p>
          </div>
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-[13px] font-medium text-primary-fg"
          >
            <Plus className="h-4 w-4" aria-hidden /> New key
          </button>
        </div>

        <div className="rounded-xl border border-line bg-surface">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-line text-[10.5px] uppercase tracking-wider text-ink-subtle">
                <th className="px-4 py-3 font-semibold">Key</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Expires</th>
                <th className="px-4 py-3 font-semibold">Last Used</th>
                <th className="px-4 py-3 font-semibold">Key limit</th>
                <th className="w-10 px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {keys.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-[13px] text-ink-subtle">
                    No API keys yet. Create one to run your agents from anywhere.
                  </td>
                </tr>
              )}
              {keys.map((key) => {
                const limit = key.credit_limit_usd ? parseFloat(key.credit_limit_usd) : null
                return (
                  <tr key={key.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        to={`/keys/${key.id}`}
                        className="text-[13px] font-medium text-ink hover:underline"
                      >
                        {key.name}
                      </Link>
                      <span className="ml-2 font-mono text-[11px] text-ink-subtle">
                        ({key.prefix.slice(-3)})
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusChip status={key.status} />
                    </td>
                    <td className="px-4 py-3 text-[12.5px] text-ink-muted">
                      {key.expires_at
                        ? new Date(key.expires_at).toLocaleDateString()
                        : 'Never'}
                    </td>
                    <td className="px-4 py-3 text-[12.5px] text-ink-muted">
                      {relative(key.last_used_at)}
                    </td>
                    <td className="px-4 py-3">
                      {limit != null ? (
                        <span className="text-[12.5px] text-ink">
                          ${limit.toLocaleString()}
                          {key.credit_reset_period && (
                            <span className="ml-1 text-[10.5px] text-ink-subtle">
                              / {key.credit_reset_period}
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-[12.5px] text-ink-muted">unlimited</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => navigate(`/keys/${key.id}`)}
                        className="text-ink-subtle hover:text-ink"
                        title="Configure"
                      >
                        <Settings2 className="h-4 w-4" aria-hidden />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="border-t border-line px-4 py-2.5 text-[11px] text-ink-subtle">
            {keys.length} key{keys.length === 1 ? '' : 's'}
          </p>
        </div>

        {!creating && (
          <p className="mt-4 flex items-center gap-2 text-[11.5px] text-ink-subtle">
            <KeyRound className="h-3.5 w-3.5" aria-hidden />
            Keys are server-side secrets — never ship one in frontend code.
          </p>
        )}
      </div>

      {creating && workspaceId && (
        <NewKeyDialog
          workspaceId={workspaceId}
          onClose={() => setCreating(false)}
          onCreated={(created) => {
            setCreating(false)
            setPlaintext(created)
            refresh()
          }}
        />
      )}
      {plaintext && <PlaintextModal created={plaintext} onClose={() => setPlaintext(null)} />}
    </div>
  )
}
