import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, Database, Loader2 } from 'lucide-react'
import {
  getConnectionSchema,
  type ConnectionTableSchema,
  type ExternalDatabase,
} from '../../api/externalDatabases'
import { Checkbox } from '../ui/Controls'

/**
 * Data-source attachment picker (D1, D4): pick connections, then the exact
 * tables/collections the agent may query. Kinds without an executor are listed but disabled —
 * "not queryable yet" — until their executor lands.
 */

export type DataSourceSelection = { id: string; tables: string[] }[]

interface DataSourcePickerProps {
  connections: ExternalDatabase[]
  value: DataSourceSelection
  onChange: (value: DataSourceSelection) => void
  error?: string
}

const QUERYABLE_KINDS = new Set(['postgres', 'mysql', 'mongodb'])

export default function DataSourcePicker({
  connections,
  value,
  onChange,
  error,
}: DataSourcePickerProps) {
  const [openId, setOpenId] = useState<string | null>(null)
  const [schemas, setSchemas] = useState<Record<string, ConnectionTableSchema[]>>({})
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const attached = new Map(value.map((item) => [item.id, item.tables]))

  useEffect(() => {
    if (!openId || schemas[openId]) return
    const workspaceId = connections.find((row) => row.id === openId)?.workspace_id
    if (!workspaceId) return
    setLoading(true)
    setLoadError(null)
    getConnectionSchema(workspaceId, openId)
      .then((schema) => setSchemas((current) => ({ ...current, [openId]: schema.tables })))
      .catch(() => setLoadError('Could not load the table list.'))
      .finally(() => setLoading(false))
  }, [openId, connections, schemas])

  const toggleAttached = (connection: ExternalDatabase) => {
    if (attached.has(connection.id)) {
      onChange(value.filter((item) => item.id !== connection.id))
    } else {
      onChange([...value, { id: connection.id, tables: [] }])
      setOpenId(connection.id)
    }
  }

  const toggleTable = (connectionId: string, qualified: string) => {
    const current = attached.get(connectionId) ?? []
    const next = current.includes(qualified)
      ? current.filter((name) => name !== qualified)
      : [...current, qualified]
    onChange(value.map((item) => (item.id === connectionId ? { ...item, tables: next } : item)))
  }

  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-ink">Data sources</span>
        <span className="font-mono text-xs text-ink-subtle">
          {value.length > 0 ? `${value.length} attached` : 'None attached'}
        </span>
      </div>

      <p className="mb-3 text-xs leading-relaxed text-ink-muted">
        Only the tables or collections you tick here are queryable by this agent — the list is a snapshot, so
        tables created later need a re-save.
      </p>
      {connections.length === 0 ? (
        <p className="text-xs text-ink-subtle">No external databases yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {connections.map((connection) => {
            const queryable = QUERYABLE_KINDS.has(connection.kind)
            const tables = attached.get(connection.id)
            const isOpen = openId === connection.id
            return (
              <li key={connection.id} className="rounded-lg border border-line">
                <div className="flex items-center gap-2 px-3 py-2 text-[13px]">
                  <button
                    type="button"
                    disabled={!queryable}
                    onClick={() => toggleAttached(connection)}
                    className={`flex-1 text-left transition-colors duration-150 ${
                      queryable ? 'hover:text-ink' : 'cursor-not-allowed opacity-50'
                    } text-ink`}
                    title={queryable ? undefined : `${connection.kind} is not queryable yet`}
                  >
                    <Database className="mr-1.5 inline w-3.5 h-3.5 text-ink-subtle" aria-hidden />
                    {connection.name}
                    <span className="ml-2 inline-flex rounded-full border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-ink-muted">
                      {queryable ? connection.kind : `${connection.kind} · not queryable yet`}
                    </span>
                  </button>
                  {queryable && tables && tables.length > 0 && (
                    <span className="font-mono text-xs text-ink-subtle">
                      {tables.length} table{tables.length === 1 ? '' : 's'}
                    </span>
                  )}
                  {queryable && tables && (
                    <button
                      type="button"
                      onClick={() => setOpenId(isOpen ? null : connection.id)}
                      className="rounded p-0.5 text-ink-subtle hover:text-ink"
                      title="Choose tables"
                    >
                      {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </button>
                  )}
                </div>
                {isOpen && tables && (
                  <div className="border-t border-line px-3.5 py-2.5">
                    {tables.length === 0 && (
                      <p className="mb-1.5 text-xs text-status-warning">
                        Choose at least one table — an attachment with no tables is refused.
                      </p>
                    )}
                    {loading && !schemas[connection.id] ? (
                      <p className="flex items-center gap-1.5 text-xs text-ink-muted">
                        <Loader2 className="w-3 h-3 animate-spin" /> Loading tables…
                      </p>
                    ) : loadError && !schemas[connection.id] ? (
                      <p className="text-xs text-status-error">{loadError}</p>
                    ) : (
                      <ul className="max-h-40 space-y-1 overflow-y-auto">
                        {(schemas[connection.id] ?? []).map((table) => {
                          const qualified = `${table.schema}.${table.name}`
                          return (
                            <li key={qualified}>
                              <label className="flex cursor-pointer items-center gap-2 text-xs">
                                <Checkbox
                                  checked={tables.includes(qualified)}
                                  onChange={() => toggleTable(connection.id, qualified)}
                                  label={qualified}
                                />
                                <span className="font-mono text-ink">{qualified}</span>
                                <span className="text-ink-subtle">
                                  ({table.columns.length} columns)
                                </span>
                              </label>
                            </li>
                          )
                        })}
                      </ul>
                    )}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
      {error && <p className="mt-1.5 text-xs text-status-error">{error}</p>}
    </div>
  )
}
