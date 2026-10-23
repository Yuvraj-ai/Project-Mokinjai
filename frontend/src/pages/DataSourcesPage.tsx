import { useEffect, useState } from 'react'
import { Database, Loader2, Plus, Trash2 } from 'lucide-react'
import { axiosDetail } from '../api/client'
import { listWorkspaces } from '../api/workspaces'
import {
  EXTERNAL_DATABASE_KINDS,
  createExternalDatabase,
  deleteExternalDatabase,
  listExternalDatabases,
  type ExternalDatabase,
  type ExternalDatabaseKind,
} from '../api/externalDatabases'

const emptyConnection = {
  name: '',
  kind: 'postgres' as ExternalDatabaseKind,
  uri: '',
  database_name: '',
  collection_name: '',
}

export default function DataSourcesPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [connections, setConnections] = useState<ExternalDatabase[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [connection, setConnection] = useState(emptyConnection)

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
      <div className="flex items-center gap-2 p-8 text-ink-400 font-body text-sm">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading connections…
      </div>
    )
  }

  return (
    <div className="p-6 space-y-8 font-body">
      {error && (
        <div className="rounded-lg border border-red-300/60 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="space-y-4">
        <h1 className="flex items-center gap-2 text-lg font-display text-ink-900 dark:text-cream-100">
          <Database className="w-4 h-4" /> Data Sources
        </h1>
        <p className="text-sm text-ink-400">
          A record is not a connection: nothing is contacted when you save one, and the URI is
          never shown again.
        </p>

        <div className="flex flex-wrap items-end gap-2">
          <input
            value={connection.name}
            onChange={(event) => setConnection({ ...connection, name: event.target.value })}
            className="w-44 rounded-lg border border-ink-100 px-3 py-2 text-sm"
            placeholder="Name"
          />
          <select
            value={connection.kind}
            onChange={(event) =>
              setConnection({ ...connection, kind: event.target.value as ExternalDatabaseKind })
            }
            className="rounded-lg border border-ink-100 px-3 py-2 text-sm"
          >
            {EXTERNAL_DATABASE_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {kind}
              </option>
            ))}
          </select>
          <input
            value={connection.uri}
            onChange={(event) => setConnection({ ...connection, uri: event.target.value })}
            className="w-80 rounded-lg border border-ink-100 px-3 py-2 text-sm font-mono"
            placeholder="postgresql://user:password@host:5432/database"
          />
          <input
            value={connection.database_name}
            onChange={(event) =>
              setConnection({ ...connection, database_name: event.target.value })
            }
            className="w-40 rounded-lg border border-ink-100 px-3 py-2 text-sm"
            placeholder="Database name"
          />
          <input
            value={connection.collection_name}
            onChange={(event) =>
              setConnection({ ...connection, collection_name: event.target.value })
            }
            className="w-40 rounded-lg border border-ink-100 px-3 py-2 text-sm"
            placeholder="Collection / index"
          />
          <button
            onClick={addConnection}
            disabled={busy || !connection.name.trim() || !connection.uri.trim()}
            className="flex items-center gap-2 rounded-lg bg-ink-800 px-4 py-2 text-sm font-medium text-cream-100 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" /> Save
          </button>
        </div>

        {connections.length === 0 ? (
          <p className="text-sm text-ink-400">No external database records yet.</p>
        ) : (
          <ul className="space-y-2">
            {connections.map((row) => (
              <li
                key={row.id}
                className="flex items-center justify-between rounded-lg border border-ink-100 px-3 py-2 text-sm"
              >
                <span className="text-ink-900">
                  {row.name}
                  <span className="ml-2 rounded bg-ink-800/5 px-2 py-0.5 text-xs text-ink-500">
                    {row.kind}
                  </span>
                  <span className="ml-2 text-xs text-ink-400">
                    {[row.database_name, row.collection_name].filter(Boolean).join(' / ') || '—'}
                  </span>
                  <span className="ml-2 text-xs text-ink-400">not verified</span>
                </span>
                <button
                  onClick={() => removeConnection(row.id)}
                  title="Delete record"
                  className="text-ink-400 hover:text-red-600"
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
