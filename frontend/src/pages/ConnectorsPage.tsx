import { useEffect, useState } from 'react'
import { Plug, Plus, RefreshCw, Trash2 } from 'lucide-react'
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
import Button from '../components/ui/Button'
import { Input, Label, Select } from '../components/ui/Field'
import { Spinner, EmptyState } from '../components/ui/Feedback'
import Badge from '../components/ui/Badge'
import { cn } from '../lib/utils'

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

const FIELD_LABELS: Record<string, string> = {
  database: 'Database name',
  path: 'Directory path',
}

const statusTones: Record<string, 'neutral' | 'success' | 'warning' | 'danger' | 'info'> = {
  enabled: 'success',
  error: 'danger',
  pending: 'warning',
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
    try {
      await deleteConnector(workspaceId, connector.id)
      setConnectors((current) => current.filter((item) => item.id !== connector.id))
      if (editingId === connector.id) setShowForm(false)
    } catch (error: unknown) {
      setConnectors((current) =>
        current.map((item) =>
          item.id === connector.id
            ? { ...item, status: 'error', last_error: axiosDetail(error) || 'Could not delete connector' }
            : item
        )
      )
    }
  }

  if (loading || !workspaceId) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner className="w-6 h-6" />
      </div>
    )
  }

  const usable = catalog.filter((item) => item.auth_type !== 'oauth')

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-ink tracking-tight leading-tight">Connectors</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Enable a connector, give it credentials, and test it to see the tools it exposes.
          </p>
        </div>
        <Button disabled={usable.length === 0} onClick={openNew}>
          <Plus className="w-4 h-4" aria-hidden /> Add connector
        </Button>
      </div>

      {showForm && entry && (
        <div className="mb-8 rounded-xl border border-line bg-surface p-5">
          <form onSubmit={(event) => {
            event.preventDefault()
            void handleSave()
          }}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label required>Connector</Label>
                <Select
                  value={entryId}
                  disabled={editingId !== null}
                  onChange={(event) => {
                    setEntryId(event.target.value)
                    setConfig({})
                    setSecret('')
                  }}
                >
                  {usable.map((item) => (
                    <option key={item.id} value={item.id}>{item.display_name}</option>
                  ))}
                </Select>
              </div>
              <div>
                <Label required>Name</Label>
                <Input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                />
              </div>
              {entry.secret_label && (
                <div className="sm:col-span-2">
                  <Label required={!editingId}>
                    {entry.secret_label} {editingId ? '(blank keeps the saved secret)' : ''}
                  </Label>
                  <Input
                    type="password"
                    value={secret}
                    onChange={(event) => setSecret(event.target.value)}
                    required={!editingId}
                    autoComplete="off"
                  />
                </div>
              )}
              {entry.config_fields.map((field) => (
                <div key={field}>
                  <Label required>{FIELD_LABELS[field] ?? field}</Label>
                  <Input
                    value={config[field] ?? ''}
                    onChange={(event) =>
                      setConfig((current) => ({ ...current, [field]: event.target.value }))
                    }
                    required
                  />
                </div>
              ))}
            </div>
            <p className="text-xs text-ink-muted">{entry.description}</p>
            {formError && (
              <p className="mt-2 text-xs text-status-error whitespace-pre-wrap">{formError}</p>
            )}
            <div className="flex items-center gap-2">
              <Button type="submit" disabled={saving} className="w-full sm:w-auto">
                {saving ? 'Saving…' : editingId ? 'Save' : 'Add connector'}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {connectors.length === 0 ? (
        <div className="bg-surface border border-line rounded-xl">
          <EmptyState
            title="No connectors yet"
            description="Add one from the catalog and test it to see the tools it exposes."
          />
        </div>
      ) : (
        <div className="space-y-3">
          {connectors.map((connector) => (
            <div key={connector.id} className="bg-surface rounded-xl border border-line p-4">
              <div className="flex items-start justify-between gap-3">
                <button onClick={() => openExisting(connector)} className="text-left">
                  <div className="text-sm font-medium text-ink">{connector.name}</div>
                  <div className="text-xs text-ink-muted mt-1">
                    {entry ? entry.display_name : ''} ·
                    {connector.transport === 'stdio' ? 'Local' : 'URL'} · {connector.auth_type} ·
                    {connector.has_auth ? 'credentials saved' : 'no credentials'}
                  </div>
                </button>
                <div className="flex items-center gap-2">
                  <Badge tone={statusTones[connector.status] ?? 'warning'}>
                    {connector.status}
                  </Badge>
                  <button
                    onClick={() => void handleTest(connector)}
                    disabled={busyId === connector.id}
                    title={connector.last_tested_at ? 'Re-test connection' : 'Test connection'}
                    className="rounded-md p-1.5 text-ink-subtle transition-colors disabled:opacity-40 hover:bg-surface-muted hover:text-ink"
                  >
                    <RefreshCw className={`w-4 h-4 ${busyId === connector.id ? 'animate-spin' : ''}`} aria-hidden />
                  </button>
                  <button
                    onClick={() => void handleDelete(connector)}
                    title="Remove"
                    aria-label={`Remove ${connector.name}`}
                    className="rounded-md p-1.5 text-ink-subtle transition-colors hover:bg-status-error-soft hover:text-status-error"
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
                      className="rounded-md border border-line bg-surface-muted px-2 py-0.5 font-mono text-[11px] text-ink-muted"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-xs text-ink-subtle">
                  {connector.status === 'pending'
                    ? 'No tools recorded — run a test.'
                    : 'The last test found no tools.'}
                </p>
              )}

              {connector.last_error && (
                <p className="mt-3 text-xs text-status-error">{connector.last_error}</p>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="mt-10">
        <h2 className="text-[13px] font-semibold text-ink mb-3">Catalog</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {catalog.map((item) => (
            <div
              key={item.id}
              className={cn(
                'bg-surface rounded-lg border border-line p-3',
                item.auth_type === 'oauth' ? 'opacity-60' : '',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-ink">{item.display_name}</span>
                <span className="font-mono text-[10px] uppercase tracking-wide text-ink-subtle">
                  {item.transport === 'stdio' ? 'Local' : 'URL'}
                </span>
              </div>
              <p className="text-xs text-ink-muted mt-1">{item.description}</p>
              {item.auth_type === 'oauth' && (
                <p className="text-[11px] font-mono text-[11px] uppercase tracking-wide text-status-warning mt-1">
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
