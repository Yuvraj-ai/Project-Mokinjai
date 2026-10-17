import { useEffect, useRef, useState } from 'react'
import { Database, Loader2, Plus, Trash2, Upload } from 'lucide-react'
import { listWorkspaces } from '../api/workspaces'
import {
  createKnowledgeBase,
  deleteDocument,
  deleteKnowledgeBase,
  downloadDocument,
  listDocuments,
  listKnowledgeBases,
  uploadDocument,
  type KnowledgeBase,
  type KnowledgeDocument,
} from '../api/knowledgeBases'
import {
  EXTERNAL_DATABASE_KINDS,
  createExternalDatabase,
  deleteExternalDatabase,
  listExternalDatabases,
  type ExternalDatabase,
  type ExternalDatabaseKind,
} from '../api/externalDatabases'

function axiosDetail(error: unknown): string | null {
  if (!error || typeof error !== 'object' || !('response' in error)) return null
  const response = error.response
  if (!response || typeof response !== 'object' || !('data' in response)) return null
  const data = response.data
  if (!data || typeof data !== 'object' || !('detail' in data)) return null
  return typeof data.detail === 'string' ? data.detail : null
}

function formatBytes(size: number | null): string {
  if (size === null) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

const emptyConnection = {
  name: '',
  kind: 'postgres' as ExternalDatabaseKind,
  uri: '',
  database_name: '',
  collection_name: '',
}

export default function KnowledgeBasePage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [selectedKbId, setSelectedKbId] = useState<string | null>(null)
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [connections, setConnections] = useState<ExternalDatabase[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [kbName, setKbName] = useState('')
  const [kbDescription, setKbDescription] = useState('')
  const [connection, setConnection] = useState(emptyConnection)
  const fileInput = useRef<HTMLInputElement>(null)

  const report = (caught: unknown, fallback: string) =>
    setError(axiosDetail(caught) ?? fallback)

  useEffect(() => {
    listWorkspaces()
      .then(async (workspaces) => {
        if (!workspaces?.length) return
        const id = workspaces[0].id
        setWorkspaceId(id)
        const [bases, databases] = await Promise.all([
          listKnowledgeBases(id),
          listExternalDatabases(id),
        ])
        setKnowledgeBases(bases)
        setConnections(databases)
        if (bases.length) {
          setSelectedKbId(bases[0].id)
          setDocuments(await listDocuments(id, bases[0].id))
        }
      })
      .catch((caught) => report(caught, 'Could not load the knowledge base'))
      .finally(() => setLoading(false))
  }, [])

  const selectKb = async (kbId: string) => {
    if (!workspaceId) return
    setSelectedKbId(kbId)
    try {
      setDocuments(await listDocuments(workspaceId, kbId))
    } catch (caught) {
      report(caught, 'Could not load the documents')
    }
  }

  const addKnowledgeBase = async () => {
    if (!workspaceId || !kbName.trim()) return
    setBusy(true)
    setError(null)
    try {
      const created = await createKnowledgeBase(workspaceId, kbName.trim(), kbDescription)
      setKnowledgeBases((current) => [created, ...current])
      setKbName('')
      setKbDescription('')
      setSelectedKbId(created.id)
      setDocuments([])
    } catch (caught) {
      report(caught, 'Could not create the knowledge base')
    } finally {
      setBusy(false)
    }
  }

  const removeKnowledgeBase = async (kbId: string) => {
    if (!workspaceId) return
    setError(null)
    try {
      await deleteKnowledgeBase(workspaceId, kbId)
      const remaining = knowledgeBases.filter((kb) => kb.id !== kbId)
      setKnowledgeBases(remaining)
      if (selectedKbId === kbId) {
        setSelectedKbId(remaining[0]?.id ?? null)
        setDocuments(remaining[0] ? await listDocuments(workspaceId, remaining[0].id) : [])
      }
    } catch (caught) {
      report(caught, 'Could not delete the knowledge base')
    }
  }

  const sendFile = async (file: File) => {
    if (!workspaceId || !selectedKbId) return
    setBusy(true)
    setError(null)
    try {
      const created = await uploadDocument(workspaceId, selectedKbId, file)
      setDocuments((current) => [created, ...current])
    } catch (caught) {
      report(caught, 'Could not upload the file')
    } finally {
      setBusy(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  const removeDocument = async (documentId: string) => {
    if (!workspaceId || !selectedKbId) return
    setError(null)
    try {
      await deleteDocument(workspaceId, selectedKbId, documentId)
      setDocuments((current) => current.filter((doc) => doc.id !== documentId))
    } catch (caught) {
      report(caught, 'Could not delete the document')
    }
  }

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
        <Loader2 className="w-4 h-4 animate-spin" /> Loading knowledge base…
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
        <h1 className="text-lg font-display text-ink-900 dark:text-cream-100">Knowledge Base</h1>

        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs text-ink-400">
            Name
            <input
              value={kbName}
              onChange={(event) => setKbName(event.target.value)}
              className="w-56 rounded-lg border border-ink-100 px-3 py-2 text-sm text-ink-900"
              placeholder="Product handbook"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-ink-400">
            Description
            <input
              value={kbDescription}
              onChange={(event) => setKbDescription(event.target.value)}
              className="w-72 rounded-lg border border-ink-100 px-3 py-2 text-sm text-ink-900"
              placeholder="Optional"
            />
          </label>
          <button
            onClick={addKnowledgeBase}
            disabled={busy || !kbName.trim()}
            className="flex items-center gap-2 rounded-lg bg-ink-800 px-4 py-2 text-sm font-medium text-cream-100 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" /> Add
          </button>
        </div>

        {knowledgeBases.length === 0 ? (
          <p className="text-sm text-ink-400">No knowledge bases yet.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {knowledgeBases.map((kb) => (
              <div
                key={kb.id}
                className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-sm ${
                  kb.id === selectedKbId
                    ? 'border-ink-800 bg-ink-800/5 text-ink-900'
                    : 'border-ink-100 text-ink-500'
                }`}
              >
                <button onClick={() => selectKb(kb.id)} className="font-medium">
                  {kb.name}
                </button>
                <button
                  onClick={() => removeKnowledgeBase(kb.id)}
                  title="Delete knowledge base"
                  className="text-ink-400 hover:text-red-600"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {selectedKbId && (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <input
                ref={fileInput}
                type="file"
                disabled={busy}
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  if (file) sendFile(file)
                }}
                className="text-sm text-ink-500 disabled:opacity-50"
              />
              <span className="flex items-center gap-1 text-xs text-ink-400">
                <Upload className="w-3 h-3" /> 25 MB max; text, markdown, CSV, JSON, PDF, DOCX, XLSX
              </span>
            </div>

            {documents.length === 0 ? (
              <p className="text-sm text-ink-400">No documents uploaded yet.</p>
            ) : (
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase text-ink-400">
                  <tr>
                    <th className="py-2">File</th>
                    <th className="py-2">Size</th>
                    <th className="py-2">Type</th>
                    <th className="py-2">Status</th>
                    <th className="py-2" />
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.id} className="border-t border-ink-100/60">
                      <td className="py-2 text-ink-900">
                        <button
                          onClick={() => {
                            if (!workspaceId) return
                            downloadDocument(
                              workspaceId,
                              doc.knowledge_base_id,
                              doc.id,
                              doc.filename ?? doc.id
                            ).catch((caught) =>
                              report(caught, 'Could not download the document')
                            )
                          }}
                          className="underline decoration-ink-200"
                        >
                          {doc.filename ?? doc.id}
                        </button>
                      </td>
                      <td className="py-2 text-ink-500">{formatBytes(doc.file_size)}</td>
                      <td className="py-2 text-ink-500">{doc.mime_type ?? '—'}</td>
                      <td className="py-2 text-ink-500" title="Stored but not extracted: text extraction is Phase 2">
                        {doc.status}
                      </td>
                      <td className="py-2 text-right">
                        <button
                          onClick={() => removeDocument(doc.id)}
                          title="Delete document"
                          className="text-ink-400 hover:text-red-600"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="flex items-center gap-2 text-lg font-display text-ink-900 dark:text-cream-100">
          <Database className="w-4 h-4" /> External databases
        </h2>
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
