import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Folder as FolderIcon,
  FolderOpen,
  FolderInput,
  Inbox,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { axiosDetail } from '../api/client'
import { listWorkspaces } from '../api/workspaces'
import {
  createFolder,
  deleteDocument,
  deleteFolder,
  downloadDocument,
  listDocuments,
  listFolders,
  moveDocuments,
  renameFolder,
  uploadDocument,
  type FileItem,
  type Folder,
} from '../api/files'

function formatBytes(size: number | null): string {
  if (size === null) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

// Mirrors ALLOWED_UPLOAD_MIME_TYPES in backend/app/routers/files.py.
const ACCEPTED_MIME_TYPES = [
  'text/plain',
  'text/markdown',
  'text/csv',
  'application/json',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
]
const ACCEPTED_MIME = ACCEPTED_MIME_TYPES.join(',')
// Linux browsers often attach an empty `type` to a File, so the extension decides then.
const ACCEPTED_EXTENSIONS = /\.(txt|md|markdown|csv|json|pdf|docx|xlsx)$/i
const MAX_UPLOAD_BYTES = 95 * 1024 * 1024

/** warmer filter value: 'all' or 'unfiled', or a folder id */
type View = 'all' | 'unfiled' | string

export default function FilesPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [folders, setFolders] = useState<Folder[]>([])
  const [files, setFiles] = useState<FileItem[]>([])
  const [view, setView] = useState<View>('all')
  const [query, setQuery] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [moveTarget, setMoveTarget] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [newFolder, setNewFolder] = useState('')
  const [renaming, setRenaming] = useState<{ id: string; value: string } | null>(null)
  const [folderDialog, setFolderDialog] = useState<Folder | null>(null)
  const [folderGate, setFolderGate] = useState(false)
  const [typedName, setTypedName] = useState('')
  const [dragOver, setDragOver] = useState<View | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const requestId = useRef(0)

  const report = (caught: unknown, fallback: string) =>
    setError(axiosDetail(caught) ?? fallback)

  const currentParams = useCallback(() => {
    const q = query.trim()
    const params: { folder_id?: string; unfiled?: boolean; q?: string } = {}
    if (view === 'unfiled') params.unfiled = true
    else if (view !== 'all') params.folder_id = view
    if (q) params.q = q
    return Object.keys(params).length ? params : undefined
  }, [view, query])

  const refresh = async (id: string) => {
    const [folderList, docList] = await Promise.all([
      listFolders(id),
      listDocuments(id, currentParams()),
    ])
    setFolders(folderList)
    setFiles(docList.documents)
    return docList.documents
  }

  useEffect(() => {
    listWorkspaces()
      .then(async (workspaces) => {
        if (!workspaces?.length) return
        const id = workspaces[0].id
        // Bootstrap loads folders and documents directly: the document effect waits
        // on workspaceId, which would load the table again.
        const [folderList, docList] = await Promise.all([
          listFolders(id),
          listDocuments(id),
        ])
        setFolders(folderList)
        setFiles(docList.documents)
        setWorkspaceId(id)
      })
      .catch((caught) => report(caught, 'Could not load the files'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!workspaceId) return
    const request = ++requestId.current
    listDocuments(workspaceId, currentParams())
      .then((data) => {
        if (requestId.current === request) setFiles(data.documents)
      })
      .catch((caught) => report(caught, 'Could not load the files'))
  }, [workspaceId, view, query, currentParams])

  const addFolder = async () => {
    if (!workspaceId || !newFolder.trim()) return
    setBusy(true)
    setError(null)
    try {
      const created = await createFolder(workspaceId, newFolder.trim())
      setFolders((current) => [...current, created])
      setNewFolder('')
    } catch (caught) {
      report(caught, 'Could not create the folder')
    } finally {
      setBusy(false)
    }
  }

  const saveRename = async () => {
    if (!workspaceId || !renaming) return setRenaming(null)
    const name = renaming.value.trim()
    const target = renaming.id
    if (!name) return setRenaming(null)
    setBusy(true)
    setError(null)
    try {
      const updated = await renameFolder(workspaceId, target, name)
      setFolders((current) => current.map((row) => (row.id === updated.id ? updated : row)))
      setRenaming(null)
    } catch (caught) {
      report(caught, 'Could not rename the folder')
    } finally {
      setBusy(false)
    }
  }

  const sendFiles = async (list: File[], folderId: string | null) => {
    if (!workspaceId || !list.length) return
    setBusy(true)
    setError(null)
    try {
      for (const file of list) {
        if (file.size > MAX_UPLOAD_BYTES) {
          setError(`“${file.name}” is larger than the 95 MB limit.`)
          continue
        }
        if (!ACCEPTED_MIME_TYPES.includes(file.type) && !ACCEPTED_EXTENSIONS.test(file.name)) {
          setError(
            `“${file.name}” is not a supported type: text, markdown, CSV, JSON, PDF, DOCX, or XLSX.`
          )
          continue
        }
        await uploadDocument(workspaceId, file, folderId)
      }
      await refresh(workspaceId)
    } catch (caught) {
      report(caught, 'Could not upload the file')
    } finally {
      setBusy(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  /** The folder page-level uploads land in: the selected folder, otherwise root. */
  const uploadTarget = (): string | null => (view === 'all' || view === 'unfiled' ? null : view)

  const dropFiles = (event: React.DragEvent<HTMLDivElement>, folderId: string | null) => {
    event.preventDefault()
    event.stopPropagation()
    setDragOver(null)
    void sendFiles(Array.from(event.dataTransfer.files ?? []), folderId)
  }

  const toggleChecked = (id: string) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    const allChecked = files.length > 0 && files.every((row) => selectedIds.has(row.id))
    setSelectedIds(allChecked ? new Set() : new Set(files.map((row) => row.id)))
  }

  const moveOne = (doc: FileItem) => {
    setSelectedIds(new Set([doc.id]))
    setMoveTarget(doc.folder_id ?? '')
    setRenaming(null)
  }

  const moveSelected = async () => {
    if (!workspaceId || selectedIds.size === 0) return
    setBusy(true)
    setError(null)
    try {
      const ids = [...selectedIds]
      await moveDocuments(workspaceId, ids, moveTarget || null)
      setSelectedIds(new Set())
      await refresh(workspaceId)
    } catch (caught) {
      report(caught, 'Could not move the files')
    } finally {
      setBusy(false)
    }
  }

  const renameInto = (row: { id: string; name: string | null }) => {
    setRenaming({ id: row.id, value: row.name ?? '' })
    setSelectedIds(new Set())
  }

  const removeFile = async (doc: FileItem) => {
    if (!workspaceId) return
    if (!window.confirm(`Delete “${doc.filename ?? doc.id}”? This cannot be undone.`)) return
    setError(null)
    try {
      await deleteDocument(workspaceId, doc.id)
      setFiles((current) => current.filter((row) => row.id !== doc.id))
      setSelectedIds((current) => {
        const next = new Set(current)
        next.delete(doc.id)
        return next
      })
      setFolders(await listFolders(workspaceId))
    } catch (caught) {
      report(caught, 'Could not delete the file')
    }
  }

  const removeEmptyFolder = async (folder: Folder) => {
    if (!workspaceId) return
    if (!window.confirm(`Delete empty folder “${folder.name}”?`)) return
    setError(null)
    try {
      await deleteFolder(workspaceId, folder.id)
      if (view === folder.id) setView('all')
      setFolders((current) => current.filter((row) => row.id !== folder.id))
    } catch (caught) {
      // A stale count or an attached file surfaces here as a 409 detail.
      report(caught, 'Could not delete the folder')
    }
  }

  const askRemoveFolder = (folder: Folder) => {
    setFolderDialog(folder)
    setFolderGate(false)
    setTypedName('')
  }

  const closeFolderDialog = () => {
    setFolderDialog(null)
    setFolderGate(false)
    setTypedName('')
  }

  const moveFolderFilesToRoot = async () => {
    if (!workspaceId || !folderDialog) return
    setBusy(true)
    setError(null)
    try {
      const inFolder = await listDocuments(workspaceId, { folder_id: folderDialog.id })
      if (inFolder.documents.length) {
        await moveDocuments(
          workspaceId,
          inFolder.documents.map((doc) => doc.id),
          null
        )
      }
      await deleteFolder(workspaceId, folderDialog.id)
      closeFolderDialog()
      await refresh(workspaceId)
    } catch (caught) {
      report(caught, 'Could not move the files and delete the folder')
    } finally {
      setBusy(false)
    }
  }

  const removeFolderForced = async () => {
    if (!workspaceId || !folderDialog || typedName !== folderDialog.name) return
    setBusy(true)
    setError(null)
    try {
      const target = folderDialog
      await deleteFolder(workspaceId, target.id, { force: true, confirm_name: typedName })
      closeFolderDialog()
      if (view === target.id) setView('all')
      await refresh(workspaceId)
    } catch (caught) {
      // The backend detail names what blocked the deletion (attached files, name mismatch).
      report(caught, 'Could not delete the folder')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-ink-400 font-body text-sm">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading files…
      </div>
    )
  }

  const destructiveReady = folderGate && typedName === folderDialog?.name

  return (
    <div
      className="p-6 font-body"
      onDragOver={(event) => {
        event.preventDefault()
        setDragOver('page')
      }}
      onDragLeave={() => setDragOver((current) => (current === 'page' ? null : current))}
      onDrop={(event) => dropFiles(event, uploadTarget())}
    >
      {error && (
        <div className="mb-6 rounded-lg border border-red-300/60 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mb-6">
        <h1 className="text-lg font-display text-ink-900 dark:text-cream-100">Files</h1>
      </div>

      <div className="flex items-start gap-8">
        <div className="w-60 shrink-0 space-y-1">
          <button
            onClick={() => setView('all')}
            className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
              view === 'all'
                ? 'border-ink-800 bg-ink-800/5 text-ink-900'
                : 'border-ink-100 text-ink-500 hover:text-ink-700'
            }`}
          >
            <FolderOpen className="w-4 h-4 shrink-0" />
            <span className="font-medium">All files</span>
          </button>
          <button
            onClick={() => setView('unfiled')}
            className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
              view === 'unfiled'
                ? 'border-ink-800 bg-ink-800/5 text-ink-900'
                : 'border-ink-100 text-ink-500 hover:text-ink-700'
            }`}
          >
            <Inbox className="w-4 h-4 shrink-0" />
            <span className="font-medium">Unfiled</span>
          </button>

          {folders.map((folder) => {
            const isRenaming = renaming?.id === folder.id
            return (
              <div
                key={folder.id}
                onDragOver={(event) => {
                  event.preventDefault()
                  event.stopPropagation()
                  setDragOver(folder.id)
                }}
                onDragLeave={(event) => {
                  event.stopPropagation()
                  setDragOver((current) => (current === folder.id ? null : current))
                }}
                onDrop={(event) => dropFiles(event, folder.id)}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                  view === folder.id
                    ? 'border-ink-800 bg-ink-800/5 text-ink-900'
                    : 'border-ink-100 text-ink-500'
                } ${dragOver === folder.id ? 'bg-ink-800/10' : ''}`}
              >
                <FolderIcon className="w-4 h-4 shrink-0" />
                {isRenaming && renaming ? (
                  <input
                    autoFocus
                    value={renaming.value}
                    onChange={(event) =>
                      setRenaming({ id: folder.id, value: event.target.value })
                    }
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') void saveRename()
                      if (event.key === 'Escape') setRenaming(null)
                    }}
                    className="w-full min-w-0 rounded border border-ink-100 px-1 py-0.5 text-sm text-ink-900"
                  />
                ) : (
                  <>
                    <button
                      onClick={() => setView(folder.id)}
                      onDoubleClick={() => renameInto(folder)}
                      className="min-w-0 flex-1 truncate text-left font-medium"
                      title={folder.name}
                    >
                      {folder.name}
                    </button>
                    <span className="shrink-0 text-xs text-ink-400">{folder.file_count}</span>
                    <button
                      onClick={() => renameInto(folder)}
                      title="Rename folder"
                      className="shrink-0 text-ink-400 hover:text-ink-700"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        if (folder.file_count === 0) void removeEmptyFolder(folder)
                        else askRemoveFolder(folder)
                      }}
                      title="Delete folder"
                      className="shrink-0 text-ink-400 hover:text-red-600"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </>
                )}
              </div>
            )
          })}

          <div className="flex gap-1 pt-2">
            <input
              value={newFolder}
              onChange={(event) => setNewFolder(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void addFolder()
              }}
              placeholder="New folder"
              className="w-full min-w-0 rounded-lg border border-ink-100 px-3 py-2 text-sm text-ink-900"
            />
            <button
              onClick={addFolder}
              disabled={busy || !newFolder.trim()}
              title="Create folder"
              className="shrink-0 rounded-lg bg-ink-800 px-2 py-2 text-sm font-medium text-cream-100 disabled:opacity-50"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileInput}
              type="file"
              multiple
              accept={ACCEPTED_MIME}
              disabled={busy}
              onChange={(event) => {
                void sendFiles(Array.from(event.target.files ?? []), uploadTarget())
              }}
              className="hidden"
            />
            <button
              onClick={() => fileInput.current?.click()}
              disabled={busy}
              className="flex items-center gap-2 rounded-lg bg-ink-800 px-4 py-2 text-sm font-medium text-cream-100 disabled:opacity-50"
            >
              <Upload className="w-4 h-4" /> Upload
            </button>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search files"
              className="w-56 rounded-lg border border-ink-100 px-3 py-2 text-sm text-ink-900"
            />
            <span className="text-xs text-ink-400">
              95 MB max; text, markdown, CSV, JSON, PDF, DOCX, or XLSX — drop files anywhere on
              this page
            </span>
          </div>

          {selectedIds.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-ink-100 bg-ink-800/5 px-3 py-2 text-sm">
              <span className="text-ink-500">{selectedIds.size} selected</span>
              <label className="flex items-center gap-2 text-xs text-ink-400">
                Move to
                <select
                  value={moveTarget}
                  onChange={(event) => setMoveTarget(event.target.value)}
                  className="rounded-lg border border-ink-100 px-2 py-1.5 text-sm text-ink-900"
                >
                  <option value="">Root</option>
                  {folders.map((folder) => (
                    <option key={folder.id} value={folder.id}>
                      {folder.name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                onClick={moveSelected}
                disabled={busy}
                className="flex items-center gap-1.5 rounded-lg bg-ink-800 px-3 py-1.5 text-sm font-medium text-cream-100 disabled:opacity-50"
              >
                <FolderInput className="w-4 h-4" /> Move
              </button>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="flex items-center gap-1 text-xs text-ink-400 hover:text-ink-700"
              >
                <X className="w-3 h-3" /> Clear
              </button>
            </div>
          )}

          {files.length === 0 ? (
            <p className="text-sm text-ink-400">
              {query.trim()
                ? `No files match “${query.trim()}”.`
                : view === 'unfiled'
                  ? 'No unfiled files.'
                  : 'No files uploaded yet.'}
            </p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-ink-400">
                <tr>
                  <th className="py-2 pr-2">
                    <input
                      type="checkbox"
                      checked={files.every((row) => selectedIds.has(row.id))}
                      onChange={toggleAll}
                    />
                  </th>
                  <th className="py-2">File</th>
                  <th className="py-2">Size</th>
                  <th className="py-2">Type</th>
                  <th className="py-2">Added</th>
                  <th className="py-2">Agents</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {files.map((doc) => {
                  const isRowMoving = selectedIds.has(doc.id)
                  return (
                    <tr key={doc.id} className="border-t border-ink-100/60">
                      <td className="py-2 pr-2">
                        <input
                          type="checkbox"
                          checked={isRowMoving}
                          onChange={() => toggleChecked(doc.id)}
                        />
                      </td>
                      <td className="py-2 text-ink-900">
                        <button
                          onClick={() => {
                            if (!workspaceId) return
                            downloadDocument(
                              workspaceId,
                              doc.id,
                              doc.filename ?? doc.id
                            ).catch((caught) =>
                              report(caught, 'Could not download the file')
                            )
                          }}
                          className="underline decoration-ink-200"
                        >
                          {doc.filename ?? doc.id}
                        </button>
                      </td>
                      <td className="py-2 text-ink-500">{formatBytes(doc.file_size)}</td>
                      <td className="py-2 text-ink-500">{doc.mime_type ?? '—'}</td>
                      <td className="py-2 text-ink-500">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-2 text-ink-500">{doc.attached_agent_count}</td>
                      <td className="py-2 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => moveOne(doc)}
                            title="Move file"
                            className="text-ink-400 hover:text-ink-700"
                          >
                            <FolderInput className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => void removeFile(doc)}
                            title="Delete file"
                            className="text-ink-400 hover:text-red-600"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {folderDialog && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-ink-900/30 p-4">
          <div className="w-full max-w-md space-y-4 rounded-lg border border-ink-100 bg-white p-5 shadow-lg dark:bg-ink-800 dark:border-ink-700">
            <h3 className="font-display text-ink-900 dark:text-cream-100">
              Delete folder “{folderDialog.name}”
            </h3>
            <p className="text-sm text-ink-500">
              This folder contains {folderDialog.file_count} file(s). Delete the folder alone?
              Move its files to the root, or delete the folder together with its files.
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={moveFolderFilesToRoot}
                disabled={busy}
                className="rounded-lg border border-ink-100 px-4 py-2 text-sm text-ink-700 disabled:opacity-50"
              >
                Move all to root
              </button>
              <button
                onClick={() => setFolderGate(true)}
                disabled={busy}
                className="rounded-lg border border-red-300/60 px-4 py-2 text-sm text-red-700 disabled:opacity-50"
              >
                Delete folder and files
              </button>
            </div>
            {folderGate && (
              <div className="space-y-2">
                <p className="text-sm text-ink-500">
                  Type the folder name exactly to confirm deletion. Files attached to agents
                  block the deletion until detached. This cannot be undone.
                </p>
                <input
                  autoFocus
                  value={typedName}
                  onChange={(event) => setTypedName(event.target.value)}
                  placeholder={folderDialog.name}
                  className="w-full rounded-lg border border-ink-100 px-3 py-2 text-sm text-ink-900"
                />
                <button
                  onClick={removeFolderForced}
                  disabled={busy || !destructiveReady}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  Delete permanently
                </button>
              </div>
            )}
            <div className="text-right">
              <button
                onClick={closeFolderDialog}
                className="text-sm text-ink-400 hover:text-ink-700"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
