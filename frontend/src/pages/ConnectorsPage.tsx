import { useEffect, useState } from 'react'
import { Loader2, Plug, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { listWorkspaces } from '../api/workspaces'
import {
  createConnector,
  deleteConnector,
  listCatalog,
  listConnectors,
  testConnector,
  updateConnector,
  type CatalogEntry,
  type Connector,
} from '../api/connectors'

function axiosDetail(error: unknown): string | null {
  if (!error || typeof error !== 'object' || !('response' in error)) return null
  const response = (error as { response?: { data?: unknown } }).response
  if (!response || typeof response !== 'object' || !('data' in response)) return null
  const data = response.data
  if (!data || typeof data !== 'object' || !('detail' in data)) return null
  const detail = (data as { detail: unknown }).detail
  if (typeof detail === 'string') return detail
  // A 422 names the offending field in a list rather than a string.
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    if (first && typeof first === 'object' && 'msg' in first && typeof first.msg === 'string') {
      return first.msg
    }
  }
  return null
}

const STATUS_STYLES: Record<string, string> = {
  enabled: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  error: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200',
  pending: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
}

const FIELD_LABELS: Record<string, string> = {
  database: 'Database name',
  path: 'Directory path',
}

export default function ConnectorsPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [catalog, setCatalog] = useState<CatalogEntry[]>([])
  const [connectors, setConnectors] = useState<Connector[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [entryId, setEntryId] = useState('')
  const [name, setName] = useState('')
  const [secret, setSecret] = useState('')
  const [config, setConfig] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    listWorkspaces()
      .then(async (workspaces) => {
        if (!workspaces?.length) return
        const id = workspaces[0].id
        setWorkspaceId(id)
        const [entries, instances] = await Promise.all([listCatalog(id), listConnectors(id)])
        setCatalog(entries)
        setConnectors(instances)
        // OAuth entries are offered but cannot be saved, so the form opens on one that can.
        setEntryId(entries.find((entry) => entry.auth_type !== 'oauth')?.id ?? '')
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const entry = catalog.find((item) => item.id === entryId) ?? null

  const openNew = () => {
    setEditingId(null)
    setName('')
    setSecret('')
    setConfig({})
    setFormError(null)
    setShowForm(true)
  }

  const openExisting = (connector: Connector) => {
    setEditingId(connector.id)
    setEntryId(connector.connector_type)
    setName(connector.name)
    setSecret('')
    setConfig(
      Object.fromEntries(Object.entries(connector.config).map(([key, value]) => [key, String(value)]))
    )
    setFormError(connector.last_error)
    setShowForm(true)
  }

  const replace = (saved: Connector) => {
    setConnectors((current) => {
      const index = current.findIndex((item) => item.id === saved.id)
      if (index < 0) return [saved, ...current]
      const next = [...current]
      next[index] = saved
      return next
    })
  }

  const handleSave = async () => {
    if (!workspaceId || !entry) return
    setSaving(true)
    setFormError(null)
    try {
      if (editingId) {
        replace(
          await updateConnector(workspaceId, editingId, {
            name: name.trim(),
            auth_secret: secret,
            config,
          })
        )
      } else {
        replace(
          await createConnector(workspaceId, {
            connector_type: entry.id,
            name: name.trim(),
            auth_secret: secret,
            config,
          })
        )
      }
      setSecret('')
      setShowForm(false)
    } catch (error: unknown) {
      setFormError(axiosDetail(error) || 'The connector could not be saved')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async (connector: Connector) => {
    if (!workspaceId) return
    setBusyId(connector.id)
    try {
      replace(await testConnector(workspaceId, connector.id))
    } catch (error: unknown) {
      setConnectors((current) =>
        current.map((item) =>
          item.id === connector.id
            ? { ...item, status: 'error', last_error: axiosDetail(error) || 'The test could not run' }
            : item
        )
      )
    } finally {
      setBusyId(null)
    }
  }

  const handleDelete = async (connector: Connector) => {
    if (!workspaceId) return
    await deleteConnector(workspaceId, connector.id)
    setConnectors((current) => current.filter((item) => item.id !== connector.id))
    if (editingId === connector.id) setShowForm(false)
  }

  if (loading || !workspaceId) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-5 h-5 text-accent animate-spin" />
      </div>
    )
  }

  const usable = catalog.filter((item) => item.auth_type !== 'oauth')

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="flex items-end justify-between mb-8">
        <div>
          <h1 className="text-3xl font-display text-ink-900 dark:text-cream-100 tracking-tight leading-none">
            Connectors
          </h1>
          <p className="text-ink-400 dark:text-ink-300 mt-2 text-sm font-body">
            Enable a connector, give it credentials, and test it to see the tools it exposes.
          </p>
        </div>
        <button
          onClick={openNew}
          disabled={usable.length === 0}
          className="inline-flex items-center gap-2 bg-ink-800 dark:bg-cream-200 hover:bg-ink-900 dark:hover:bg-cream-300 text-cream-50 dark:text-ink-800 font-body font-medium py-2 px-5 rounded-lg text-sm disabled:opacity-60"
        >
          <Plus className="w-4 h-4" /> Add connector
        </button>
      </div>

      {showForm && entry && (
        <form
          className="mb-8 rounded-xl border border-ink-100/60 dark:border-ink-700/60 bg-white dark:bg-ink-800 p-5 space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            void handleSave()
          }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block text-xs font-body text-ink-400">
              Connector
              <select
                value={entryId}
                disabled={editingId !== null}
                onChange={(event) => {
                  setEntryId(event.target.value)
                  setConfig({})
                  setSecret('')
                }}
                className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100 disabled:opacity-60"
              >
                {usable.map((item) => (
                  <option key={item.id} value={item.id}>{item.display_name}</option>
                ))}
              </select>
            </label>
            <label className="block text-xs font-body text-ink-400">
              Name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100"
              />
            </label>
            {entry.secret_label && (
              <label className="block text-xs font-body text-ink-400 sm:col-span-2">
                {entry.secret_label} {editingId ? '(blank keeps the saved secret)' : ''}
                <input
                  type="password"
                  value={secret}
                  onChange={(event) => setSecret(event.target.value)}
                  required={!editingId}
                  autoComplete="off"
                  className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100"
                />
              </label>
            )}
            {entry.config_fields.map((field) => (
              <label key={field} className="block text-xs font-body text-ink-400">
                {FIELD_LABELS[field] ?? field}
                <input
                  value={config[field] ?? ''}
                  onChange={(event) =>
                    setConfig((current) => ({ ...current, [field]: event.target.value }))
                  }
                  required
                  className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100"
                />
              </label>
            ))}
          </div>
          <p className="text-xs font-body text-ink-400">{entry.description}</p>
          {formError && (
            <p className="text-sm font-body text-status-error whitespace-pre-wrap">{formError}</p>
          )}
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 bg-ink-800 dark:bg-cream-200 text-cream-50 dark:text-ink-800 font-body font-medium py-2 px-5 rounded-lg text-sm disabled:opacity-60"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {editingId ? 'Save' : 'Add connector'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="text-sm font-body text-ink-400 hover:text-ink-700 dark:hover:text-cream-200"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {connectors.length === 0 ? (
        <div className="text-center py-20">
          <Plug className="w-10 h-10 text-cream-300 dark:text-ink-600 mx-auto mb-4" strokeWidth={1.5} />
          <h3 className="text-2xl font-display italic text-ink-900 dark:text-cream-100 mb-2">
            No connectors yet
          </h3>
          <p className="text-sm text-ink-400 dark:text-ink-300 font-body">
            Add one from the catalog and test it to see the tools it exposes.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {connectors.map((connector) => (
            <div
              key={connector.id}
              className="rounded-xl border border-ink-100/60 dark:border-ink-700/60 bg-white dark:bg-ink-800 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <button onClick={() => openExisting(connector)} className="text-left">
                  <div className="font-body font-medium text-ink-900 dark:text-cream-100">
                    {connector.name}
                  </div>
                  <div className="text-xs text-ink-400 mt-1">
                    {connector.display_name} ·{' '}
                    {connector.transport === 'stdio' ? 'Local' : 'URL'} · {connector.auth_type}
                    {' · '}
                    {connector.has_auth ? 'credentials saved' : 'no credentials'}
                  </div>
                </button>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-[10px] uppercase tracking-wide font-semibold px-2 py-1 rounded ${
                      STATUS_STYLES[connector.status] ?? STATUS_STYLES.pending
                    }`}
                  >
                    {connector.status}
                  </span>
                  <button
                    onClick={() => void handleTest(connector)}
                    disabled={busyId === connector.id}
                    title="Test connection"
                    className="text-ink-400 hover:text-ink-800 dark:hover:text-cream-100 disabled:opacity-40"
                  >
                    <RefreshCw
                      className={`w-4 h-4 ${busyId === connector.id ? 'animate-spin' : ''}`}
                    />
                  </button>
                  <button
                    onClick={() => void handleDelete(connector)}
                    title="Remove"
                    className="text-ink-300 hover:text-status-error"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {connector.tools.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {connector.tools.map((tool) => (
                    <span
                      key={tool}
                      className="text-[11px] font-mono px-2 py-0.5 rounded bg-ink-100/70 dark:bg-ink-700/60 text-ink-600 dark:text-cream-200"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-xs font-body text-ink-400">
                  {connector.status === 'pending'
                    ? 'No tools recorded — run a test.'
                    : 'The last test found no tools.'}
                </p>
              )}

              {connector.last_error && (
                <p className="mt-3 text-sm font-body text-status-error">{connector.last_error}</p>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="mt-10">
        <h2 className="text-xs uppercase tracking-wide font-body text-ink-400 mb-3">Catalog</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {catalog.map((item) => (
            <div
              key={item.id}
              className={`rounded-lg border border-ink-100/60 dark:border-ink-700/60 p-3 ${
                item.auth_type === 'oauth' ? 'opacity-60' : ''
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-body text-sm text-ink-800 dark:text-cream-100">
                  {item.display_name}
                </span>
                <span className="text-[10px] uppercase tracking-wide text-ink-400">
                  {item.transport === 'stdio' ? 'Local' : 'URL'}
                </span>
              </div>
              <p className="text-xs text-ink-400 mt-1">{item.description}</p>
              {item.auth_type === 'oauth' && (
                <p className="text-[11px] text-amber-600 dark:text-amber-300 mt-1">
                  OAuth — not yet supported
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
