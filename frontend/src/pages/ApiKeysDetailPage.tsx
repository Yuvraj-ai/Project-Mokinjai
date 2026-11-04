import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import {
  disableApiKey,
  enableApiKey,
  getApiKey,
  getApiKeyLogs,
  getApiKeyUsage,
  revokeApiKey,
  rotateApiKey,
  updateApiKey,
  type ApiKeyRow,
  type ApiKeyUsage,
  type KeyLogRow,
} from '../api/apiKeys'
import { PlaintextModal, StatusChip } from './ApiKeysPage'
import { cn } from '../lib/utils'

function BudgetRing({ spend, limit }: { spend: number; limit: number | null }) {
  if (limit == null) {
    return (
      <div className="flex items-center gap-3">
        <div className="flex h-14 w-14 items-center justify-center rounded-full border-2 border-line text-[10px] text-ink-subtle">
          ∞
        </div>
        <div>
          <p className="text-[12.5px] font-medium text-ink">No key limit</p>
          <p className="text-[11.5px] text-ink-subtle">${spend.toFixed(2)} spent this window</p>
        </div>
      </div>
    )
  }
  const fraction = limit > 0 ? Math.min(1, spend / limit) : 0
  const degrees = Math.round(fraction * 360)
  return (
    <div className="flex items-center gap-3">
      <div
        className="flex h-14 w-14 items-center justify-center rounded-full"
        style={{
          background: `conic-gradient(var(--color-primary) ${degrees}deg, var(--color-line) ${degrees}deg)`,
        }}
      >
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-surface text-[10.5px] text-ink-muted">
          {Math.round(fraction * 100)}%
        </div>
      </div>
      <div>
        <p className="text-[12.5px] font-medium text-ink">Key limit</p>
        <p className="text-[11.5px] text-ink-muted">
          ${spend.toFixed(2)} / ${limit.toFixed(2)}
        </p>
        <p className="text-[11px] text-ink-subtle">${Math.max(0, limit - spend).toFixed(2)} remaining</p>
      </div>
    </div>
  )
}

function SpendChart({ daily }: { daily: { date: string; cost: number }[] }) {
  const max = Math.max(...daily.map((d) => d.cost), 0.000001)
  return (
    <div className="flex h-28 items-end gap-1">
      {daily.map((day) => (
        <div
          key={day.date}
          title={`${day.date}: $${day.cost.toFixed(4)}`}
          className="min-w-[3px] flex-1 rounded-t-sm bg-primary/70"
          style={{ height: `${Math.max(2, (day.cost / max) * 100)}%`, opacity: day.cost > 0 ? 1 : 0.25 }}
        />
      ))}
    </div>
  )
}

export default function ApiKeysDetailPage() {
  const { keyId } = useParams()
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [key, setKey] = useState<ApiKeyRow | null>(null)
  const [usage, setUsage] = useState<ApiKeyUsage | null>(null)
  const [logs, setLogs] = useState<KeyLogRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [plaintext, setPlaintext] = useState<string | null>(null)
  const [confirmRotate, setConfirmRotate] = useState(false)

  useEffect(() => {
    import('../api/workspaces').then(({ listWorkspaces }) =>
      listWorkspaces().then((workspaces) => {
        if (workspaces.length > 0) setWorkspaceId(workspaces[0].id)
      })
    )
  }, [])

  const refresh = useCallback(() => {
    if (!workspaceId || !keyId) return
    getApiKey(workspaceId, keyId).then(setKey).catch(() => setError('Could not load the key.'))
    getApiKeyUsage(workspaceId, keyId).then(setUsage).catch(() => {})
    getApiKeyLogs(workspaceId, keyId).then(setLogs).catch(() => {})
  }, [workspaceId, keyId])

  useEffect(refresh, [refresh])

  const act = async (action: () => Promise<unknown>) => {
    if (!workspaceId || !keyId) return
    try {
      await action()
      refresh()
    } catch {
      setError('The action failed.')
    }
  }

  if (!key) {
    return (
      <div className="flex h-full items-center justify-center text-[13px] text-ink-subtle">
        {error ?? 'Loading…'}
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-8">
      <div className="mx-auto max-w-4xl">
        <Link to="/api-keys" className="flex items-center gap-1 text-[12px] text-ink-subtle hover:text-ink">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> API keys
        </Link>

        <div className="mb-6 mt-3 flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-ink">{key.name}</h1>
          <StatusChip status={key.status} />
        </div>
        <p className="mb-6 font-mono text-[12px] text-ink-subtle">{key.prefix}…</p>

        {/* Settings */}
        <div className="mb-6 space-y-5 rounded-xl border border-line bg-surface p-6">
          <div>
            <label className="mb-1 block text-[12.5px] font-medium text-ink">Name</label>
            <input
              defaultValue={key.name}
              onBlur={(event) => {
                if (event.target.value.trim() && event.target.value !== key.name) {
                  void act(() => updateApiKey(workspaceId!, keyId!, { name: event.target.value.trim() }))
                }
              }}
              className="w-full rounded-lg border border-line bg-surface-muted px-3 py-2 text-[13px] text-ink focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <p className="mt-1 text-[11px] text-ink-subtle">
              Choose a clear, descriptive name to identify this key.
            </p>
          </div>
          <div>
            <label className="mb-1 block text-[12.5px] font-medium text-ink">Expiration</label>
            <p className="text-[13px] text-ink">
              {key.expires_at ? new Date(key.expires_at).toLocaleString() : 'Never'}
            </p>
            <p className="mt-1 text-[11px] text-ink-subtle">
              Expiration cannot be modified. Create a new API key for a new expiration time.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-[12.5px] font-medium text-ink">Credit limit ($)</label>
              <input
                defaultValue={key.credit_limit_usd ?? ''}
                placeholder="Blank for unlimited"
                inputMode="decimal"
                onBlur={(event) => {
                  const value = event.target.value.trim() || null
                  if (value !== (key.credit_limit_usd ?? null)) {
                    void act(() => updateApiKey(workspaceId!, keyId!, { credit_limit_usd: value }))
                  }
                }}
                className="w-full rounded-lg border border-line bg-surface-muted px-3 py-2 text-[13px] text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p className="mt-1 text-[11px] text-ink-subtle">
                Once the credits ($USD) consumed by this key reach this amount, the key stops working.
              </p>
            </div>
            <div>
              <label className="mb-1 block text-[12.5px] font-medium text-ink">Reset limit</label>
              <select
                defaultValue={key.credit_reset_period ?? ''}
                onChange={(event) =>
                  void act(() =>
                    updateApiKey(workspaceId!, keyId!, {
                      credit_reset_period: (event.target.value || null) as never,
                    })
                  )
                }
                className="w-full rounded-lg border border-line bg-surface-muted px-3 py-2 text-[13px] text-ink focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">N/A (lifetime total)</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
              <p className="mt-1 text-[11px] text-ink-subtle">
                Daily at midnight UTC, weekly on Monday, monthly on the 1st.
              </p>
            </div>
          </div>
        </div>

        {/* Usage */}
        {usage && (
          <div className="mb-6 rounded-xl border border-line bg-surface p-6">
            <p className="text-[12.5px] text-ink-muted">Spend in current window</p>
            <p className="mb-4 text-2xl font-semibold text-ink">${usage.window_spend.toFixed(2)}</p>
            <BudgetRing spend={usage.window_spend} limit={usage.window_limit} />
            <p className="mb-2 mt-6 text-[12.5px] font-medium text-ink">Spend in last 30 days</p>
            <SpendChart daily={usage.daily} />
            <div className="mt-6 grid grid-cols-4 gap-4 border-t border-line pt-4">
              {(['today', 'week', 'month', 'total'] as const).map((bucket) => (
                <div key={bucket}>
                  <p className="text-[11px] uppercase tracking-wider text-ink-subtle">{bucket}</p>
                  <p className="text-[15px] font-medium text-ink">${usage.totals[bucket].toFixed(4)}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Logs */}
        <div className="mb-6 rounded-xl border border-line bg-surface">
          <p className="border-b border-line px-6 py-4 text-[12.5px] font-semibold uppercase tracking-wider text-ink-subtle">
            Logs
          </p>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-line text-[10.5px] uppercase tracking-wider text-ink-subtle">
                <th className="px-6 py-2.5 font-semibold">Date</th>
                <th className="px-6 py-2.5 font-semibold">Status</th>
                <th className="px-6 py-2.5 font-semibold">Tokens</th>
                <th className="px-6 py-2.5 font-semibold">Cost</th>
                <th className="px-6 py-2.5 font-semibold">Duration</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-[13px] text-ink-subtle">
                    No transactions found. Try calling the API with this key.
                  </td>
                </tr>
              )}
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-line last:border-0">
                  <td className="px-6 py-2.5 text-[12.5px] text-ink">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-2.5 text-[12.5px]">
                    <span
                      className={cn(
                        log.status === 'completed' ? 'text-status-success' : 'text-status-error'
                      )}
                    >
                      {log.status}
                    </span>
                  </td>
                  <td className="px-6 py-2.5 text-[12.5px] text-ink-muted">—</td>
                  <td className="px-6 py-2.5 text-[12.5px] text-ink-muted">
                    ${log.cost_usd ? parseFloat(log.cost_usd).toFixed(6) : '0.000000'}
                  </td>
                  <td className="px-6 py-2.5 text-[12.5px] text-ink-muted">
                    {log.execution_time_ms != null ? `${(log.execution_time_ms / 1000).toFixed(1)}s` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Danger zone */}
        <div className="space-y-3 rounded-xl border border-status-error/30 bg-surface p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-[13px] font-medium text-status-error">Disable key</p>
              <p className="text-[11.5px] text-ink-muted">
                Prevent this key from being used. You can re-enable it later.
              </p>
            </div>
            <button
              onClick={() => void act(() => (key.status === 'disabled' ? enableApiKey(workspaceId!, keyId!) : disableApiKey(workspaceId!, keyId!)))}
              className="rounded-lg border border-status-error px-4 py-2 text-[12.5px] font-medium text-status-error hover:bg-status-error-soft"
            >
              {key.status === 'disabled' ? 'Enable' : 'Disable'}
            </button>
          </div>
          <div className="flex items-center justify-between gap-4 border-t border-line pt-3">
            <div>
              <p className="text-[13px] font-medium text-status-error">Rotate key</p>
              <p className="text-[11.5px] text-ink-muted">
                Replace the secret. The old key stops working immediately; the new one is shown once.
              </p>
            </div>
            <button
              onClick={() => setConfirmRotate(true)}
              className="rounded-lg border border-line px-4 py-2 text-[12.5px] font-medium text-ink-muted hover:text-ink"
            >
              Rotate
            </button>
          </div>
          <div className="flex items-center justify-between gap-4 border-t border-line pt-3">
            <div>
              <p className="text-[13px] font-medium text-status-error">Delete key</p>
              <p className="text-[11.5px] text-ink-muted">
                Permanently revoke this key. This action cannot be undone.
              </p>
            </div>
            <button
              onClick={() => {
                if (confirmDelete) {
                  void act(() => revokeApiKey(workspaceId!, keyId!)).then(() => {
                    window.location.href = '/api-keys'
                  })
                } else {
                  setConfirmDelete(true)
                }
              }}
              className={cn(
                'rounded-lg px-4 py-2 text-[12.5px] font-medium',
                confirmDelete
                  ? 'bg-status-error text-white'
                  : 'bg-status-error-soft text-status-error hover:bg-status-error hover:text-white'
              )}
            >
              {confirmDelete ? 'Confirm delete' : 'Delete'}
            </button>
          </div>
        </div>

        {error && <p className="mt-4 text-[12.5px] text-status-error">{error}</p>}
      </div>

      {plaintext && <PlaintextModal created={{ id: key.id, key: plaintext } as never} onClose={() => setPlaintext(null)} />}
      {confirmRotate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-sm rounded-xl border border-line bg-surface p-6">
            <h2 className="text-[15px] font-semibold text-ink">Rotate this key?</h2>
            <p className="mt-2 text-[12.5px] text-ink-muted">
              The current secret stops working the moment the new one is issued. Any
              integration using it must be updated.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setConfirmRotate(false)}
                className="rounded-lg border border-line px-3 py-2 text-[12.5px] text-ink-muted"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  setConfirmRotate(false)
                  if (!workspaceId || !keyId) return
                  try {
                    const rotated = await rotateApiKey(workspaceId, keyId)
                    setPlaintext(rotated.key)
                    refresh()
                  } catch {
                    setError('Rotation failed.')
                  }
                }}
                className="rounded-lg bg-primary px-3 py-2 text-[12.5px] font-medium text-primary-fg"
              >
                Rotate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
