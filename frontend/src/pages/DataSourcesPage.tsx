import { useEffect, useState } from 'react'
import { Database, Loader2, Plus, Trash2 } from 'lucide-react'
import { axiosDetail } from '../api/client'
import { listWorkspaces } from '../api/workspaces'
import {
  EXTERNAL_DATABASE_KINDS,
  createExternalDatabase,
  deleteExternalDatabase,
  getConnectionSchema,
  listExternalDatabases,
  type ExternalDatabase,
  type ExternalDatabaseKind,
} from '../api/externalDatabases'
import Button from '../components/ui/Button'
import { Input, Label, Select } from '../components/ui/Field'
import { Callout, Spinner } from '../components/ui/Feedback'

type CheckState = { status: 'checking' } | { status: 'ok'; tables: number } | { status: 'failed'; message: string }

const emptyConnection = {
  name: '',
  kind: 'postgres' as ExternalDatabaseKind,
  uri: '',
  database_name: '',
  collection_name: '',
}

function CheckBadge({ state }: { state: CheckState | undefined }) {
  if (!state) return <span className="ml-2 font-mono text-[11px] text-ink-subtle">not verified</span>
  if (state.status === 'checking') {
    return <span className="ml-2 text-xs text-ink-muted">checking…</span>
  }
  if (state.status === 'ok') {
    return (
      <span className="ml-2 inline-flex rounded-full bg-status-success-soft px-2 py-0.5 text-[11px] font-medium text-status-success">
        connected · {state.tables} table{state.tables === 1 ? '' : 's'}
      </span>
    )
  }
  return (
    <span className="ml-2 inline-flex rounded-full bg-status-error-soft px-2 py-0.5 text-[11px] font-medium text-status-error">
      {state.message}
    </span>
  )
}

export default function DataSourcesPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [connections, setConnections] = useState<ExternalDatabase[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [connection, setConnection] = useState(emptyConnection)
  const [checks, setChecks] = useState<Record<string, CheckState>>({})

  const report = (caught: unknown, fallback: string) =>
    setError(axiosDetail(caught) ?? fallback)

  useEffect(() => {
    listWorkspaces()
      .then(async (workspaces) => {
        if (!workspaces?.length) return
        const id = workspaces[0].id
        setWorkspaceId(id)
        setConnections(await listExternalDatabases(id))
      })
      .catch((caught) => report(caught, 'Could not load the connections'))
      .finally(() => setLoading(false))
  }, [])

  const addConnection = async () => {
    if (!workspaceId || !connection.name.trim() || !connection.uri.trim()) return
    setBusy(true)
    setError(null)
    try {
      const created = await createExternalDatabase(workspaceId, {
        name: connection.name.trim(),
        kind: connection.kind,
        uri: connection.uri.trim(),
        database_name: connection.database_name.trim() || null,
        collection_name: connection.collection_name.trim() || null,
      })
      setConnections((current) => [created, ...current])
      setConnection(emptyConnection)
    } catch (caught) {
      report(caught, 'Could not save the connection record')
    } finally {
      setBusy(false)
    }
  }

  const checkConnection = async (connectionId: string) => {
    if (!workspaceId) return
    setError(null)
    setChecks((current) => ({ ...current, [connectionId]: { status: 'checking' } }))
    try {
      const schema = await getConnectionSchema(workspaceId, connectionId)
      setChecks((current) => ({
        ...current,
        [connectionId]: { status: 'ok', tables: schema.tables.length },
      }))
    } catch (caught) {
      setChecks((current) => ({
        ...current,
        [connectionId]: {
          status: 'failed',
          message: axiosDetail(caught) ?? 'Connection failed',
        },
      }))
    }
  }

  const removeConnection = async (connectionId: string) => {
    if (!workspaceId) return
    setError(null)
    try {
      await deleteExternalDatabase(workspaceId, connectionId)
      setConnections((current) => current.filter((row) => row.id !== connectionId))
    } catch (caught) {
      report(caught, 'Could not delete the connection record')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-sm text-ink-muted">
        <Spinner /> Loading connections…
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-8 py-10 space-y-6">
      {error && (
        <div className="rounded-lg bg-status-error-soft px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}

      <section className="space-y-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold text-ink tracking-tight">
            <Database className="w-5 h-5" aria-hidden /> Data Sources
          </h1>
          <p className="mt-1 text-sm text-ink-muted">
            A record is not a connection: nothing is contacted when you save one, and the URI is
            never shown again.
          </p>
        </div>

        <Callout tone="info" title="Use a read-only database role">
          <p className="leading-relaxed">
            Every agent query runs through five safety layers (parsed SELECT-only validation, a
            read-only transaction, your per-agent table selection, timeouts and row caps, and an
            audit log) — but the strongest boundary is the database account itself. Connect with a
            least-privilege read-only role.
          </p>
          <p className="mt-1.5 leading-relaxed">
            Know the limits: read-only does not stop the agent from reading whatever the query
            returns, so the per-agent table selection is the mitigation that matters. And if you
            connect with a write-capable role, you are trusting the agent with it.
          </p>
        </Callout>

        <div className="bg-surface border border-line rounded-xl p-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <Label required>Name</Label>
              <Input
                value={connection.name}
                onChange={(event) => setConnection({ ...connection, name: event.target.value })}
                placeholder="Analytics replica"
              />
            </div>
            <div>
              <Label>Kind</Label>
              <Select
                value={connection.kind}
                onChange={(event) =>
                  setConnection({ ...connection, kind: event.target.value as ExternalDatabaseKind })
                }
              >
                {EXTERNAL_DATABASE_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {kind}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label required>URI</Label>
              <Input
                value={connection.uri}
                onChange={(event) => setConnection({ ...connection, uri: event.target.value })}
                className="font-mono"
                placeholder="postgresql://user:password@host:5432/database"
              />
            </div>
            <div>
              <Label>Database name</Label>
              <Input
                value={connection.database_name}
                onChange={(event) =>
                  setConnection({ ...connection, database_name: event.target.value })
                }
                placeholder="Optional"
              />
            </div>
            <div>
              <Label>Collection / index</Label>
              <Input
                value={connection.collection_name}
                onChange={(event) =>
                  setConnection({ ...connection, collection_name: event.target.value })
                }
                placeholder="Optional"
              />
            </div>
            <div className="flex items-end">
              <Button
                onClick={addConnection}
                loading={busy}
                disabled={!connection.name.trim() || !connection.uri.trim()}
              >
                <Plus className="w-4 h-4" aria-hidden /> Save
              </Button>
            </div>
          </div>
        </div>

        {connections.length === 0 ? (
          <p className="text-sm text-ink-subtle">No external database records yet.</p>
        ) : (
          <ul className="space-y-2">
            {connections.map((row) => (
              <li
                key={row.id}
                className="flex items-center justify-between bg-surface rounded-lg border border-line px-4 py-3 text-sm"
              >
                <span className="text-ink">
                  {row.name}
                  <span className="ml-2.5 inline-flex rounded-full border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-ink-muted">
                    {row.kind}
                  </span>
                  <span className="ml-2.5 text-xs text-ink-subtle">
                    {[row.database_name, row.collection_name].filter(Boolean).join(' / ') || '—'}
                  </span>
                  <CheckBadge state={checks[row.id]} />
                  <button
                    onClick={() => checkConnection(row.id)}
                    title="Check connection"
                    className="ml-2 inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs text-ink-muted hover:bg-surface-muted hover:text-ink disabled:opacity-50 transition-colors"
                    disabled={checks[row.id]?.status === 'checking'}
                  >
                    {checks[row.id]?.status === 'checking' ? (
                      <Loader2 className="w-3 h-3 animate-spin" aria-hidden />
                    ) : null}
                    Check
                  </button>
                </span>
                <button
                  onClick={() => removeConnection(row.id)}
                  title="Delete record"
                  aria-label={`Delete ${row.name}`}
                  className="rounded-md p-1.5 text-ink-subtle transition-colors hover:bg-status-error-soft hover:text-status-error"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
