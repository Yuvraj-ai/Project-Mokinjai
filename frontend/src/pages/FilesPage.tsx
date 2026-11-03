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
import Button from '../components/ui/Button'
import { Spinner } from '../components/ui/Feedback'
import { cn } from '../lib/utils'

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
      <div className="flex items-center gap-2 p-8 text-sm text-ink-muted">
        <Spinner /> Loading files…
      </div>
    )
  }

  const destructiveReady = folderGate && typedName === folderDialog?.name

  return (
    <div
      className="p-6"
      onDragOver={(event) => {
        event.preventDefault()
        setDragOver('page')
      }}
      onDragLeave={() => setDragOver((current) => (current === 'page' ? null : current))}
      onDrop={(event) => dropFiles(event, uploadTarget())}
    >
      {error && (
        <div className="mb-6 rounded-lg bg-status-error-soft px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}

      <div className="mb-6">
        <h1 className="text-xl font-semibold text-ink">Files</h1>
      </div>

      <div className="flex items-start gap-8">
        <div className="w-60 shrink-0 space-y-1">
          <button
            onClick={() => setView('all')}
            className={cn(
              'flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-sm',
              view === 'all'
                ? 'border-line bg-surface muted text-ink font-medium'
                : 'border-line text-ink-subtle hover:text-ink hover:bg-surface-muted',
            )}
          >
            <FolderOpen className="w-4 h-4 shrink-0" aria-hidden />
            <span className="font-medium">All files</span>
          </button>
          <button
            onClick={() => setView('unfiled')}
            className={cn(
              'flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-sm',
              view === 'unfiled'
                ? 'border-line bg-surface muted text-ink font-medium'
                : 'border-line text-ink-subtle hover:text-ink hover:bg-surface-muted',
            )}
          >
            <Inbox className="w-4 h-4 shrink-0" aria-hidden />
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
                className={cn(
                  'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors duration-150',
                  view === folder.id ? 'bg-surface-muted text-ink font-medium border-line' : 'text-ink-subtle border-line hover:text-ink hover:bg-surface-muted',
                  dragOver === folder.id ? 'bg-surface-muted' : '',
                )}
              >
                <FolderIcon className="w-4 h-4 shrink-0" aria-hidden />
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
                    className="w-full min-w-0 rounded-lg border border-line bg-surface px-1 py-0.5 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                ) : (
                  <>
                    <button
                      onClick={() => setView(folder.id)}
                      onDoubleClick={() => renameInto(folder)}
                      className="min-w-0 flex-1 truncate text-left text-sm text-ink font-medium"
                      title={folder.name}
                    >
                      {folder.name}
                    </button>
                    <span className="font-mono text-xs text-ink-subtle">{folder.file_count}</span>
                    <button
                      onClick={() => renameInto(folder)}
                      title="Rename folder"
                      className="shrink-0 rounded p-1 text-ink-subtle hover:bg-surface-muted hover:text-ink transition-colors"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        if (folder.file_count === 0) void removeEmptyFolder(folder)
                        else askRemoveFolder(folder)
                      }}
                      title="Delete folder"
                      className="shrink-0 rounded p-1 text-ink-subtle hover:bg-status-error-soft hover:text-status-error transition-colors"
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
              className="w-full min-w-0 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <Button disabled={busy || !newFolder.trim()} title="Create folder">
              <Plus className="w-4 h-4" aria-hidden />
            </Button>
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
            <Button disabled={busy}>
              <Upload className="w-4 h-4" aria-hidden /> Upload
            </Button>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search files"
              className="w-56 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <span className="text-xs text-ink-subtle">
              95 MB max; text, markdown, CSV, JSON, PDF, DOCX, or XLSX — drop files anywhere on
              this page
            </span>
          </div>

          {selectedIds.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-surface-muted px-3 py-2 text-sm">
              <span className="font-mono text-xs text-ink-muted">{selectedIds.size} selected</span>
              <label className="flex items-center gap-2 text-[13px] text-ink-muted">
                Move to
                <select
                  value={moveTarget}
                  onChange={(event) => setMoveTarget(event.target.value)}
                  className="rounded-md border border-line bg-surface px-2 py-1 text-sm text-ink"
                >
                  <option value="">Root</option>
                  {folders.map((folder) => (
                    <option key={folder.id} value={folder.id}>
                      {folder.name}
                    </option>
                  ))}
                </select>
              </label>
              <Button size="sm" disabled={busy} onClick={moveSelected}>
                <FolderInput className="w-4 h-4" aria-hidden /> Move
              </Button>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="flex items-center gap-1 text-xs text-ink-subtle hover:text-ink transition-colors"
              >
                <X className="w-3 h-3" aria-hidden /> Clear
              </button>
            </div>
          )}

          {files.length === 0 ? (
            <p className="text-sm text-ink-subtle">
              {query.trim()
                ? `No files match “${query.trim()}”.`
                : view === 'unfiled'
                  ? 'No unfiled files.'
                  : 'No files uploaded yet.'}
            </p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="bg-surface-muted border-b border-line">
                  <th className="py-2 pr-2">
                    <input
                      type="checkbox"
                      checked={files.every((row) => selectedIds.has(row.id))}
                      onChange={toggleAll}
                      className="accent-primary"
                    />
                  </th>
                  <th className="py-2 font-medium text-[13px] text-ink-muted uppercase tracking-wide">File</th>
                  <th className="py-2 font-medium text-[13px] text-ink-muted uppercase tracking-wide">Size</th>
                  <th className="py-2 font-medium text-[13px] text-ink-muted uppercase tracking-wide">Type</th>
                  <th className="py-2 font-medium text-[13px] text-ink-muted uppercase tracking-wide">Added</th>
                  <th className="py-2 font-medium text-[13px] text-ink-muted uppercase tracking-wide">Agents</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {files.map((doc) => {
                  const isRowMoving = selectedIds.has(doc.id)
                  return (
                    <tr key={doc.id} className={cn('transition-colors duration-150', isRowMoving && 'bg-surface-muted')}>
                      <td className="py-2 pr-2">
                        <input
                          type="checkbox"
                          checked={isRowMoving}
                          onChange={() => toggleChecked(doc.id)}
                          className="accent-primary"
                        />
                      </td>
                      <td className="py-2 text-ink">
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
                          className="text-ink font-medium underline underline-offset-4 hover:text-primary hover:decoration-primary transition-colors"
                        >
                          {doc.filename ?? doc.id}
                        </button>
                      </td>
                      <td className="py-2 font-mono text-[13px] text-ink-subtle">{formatBytes(doc.file_size)}</td>
                      <td className="py-2 text-[13px] text-ink-subtle">{doc.mime_type ?? '—'}</td>
                      <td className="py-2 text-[13px] text-ink-subtle">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-2 font-mono text-[11px] text-ink-muted">
                        {doc.attached_agent_count}
                      </td>
                      <td className="py-2 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => moveOne(doc)}
                            title="Move file"
                            className="rounded p-1.5 text-ink-subtle hover:bg-surface-muted hover:text-ink transition-colors"
                          >
                            <FolderInput className="w-4 h-4" aria-hidden />
                          </button>
                          <button
                            onClick={() => void removeFile(doc)}
                            title="Delete file"
                            className="rounded p-1.5 text-ink-subtle hover:bg-status-error-soft hover:text-status-error transition-colors"
                          >
                            <Trash2 className="w-4 h-4" aria-hidden />
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 dark:bg-black/60 p-2 sm:p-4">
          <div className="m-auto w-full max-w-md rounded-2xl border border-line bg-surface p-5 shadow-drawer animate-scale-in">
            <h3 className="text-base font-semibold text-ink">
              Delete folder “{folderDialog.name}”
            </h3>
            <p className="mt-1 text-xs text-ink-muted">
              This folder contains {folderDialog.file_count} file(s). Delete the folder alone?
              Move its files to the root, or delete the folder together with its files.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={moveFolderFilesToRoot}
              >
                Move all to root
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={busy}
                onClick={() => setFolderGate(true)}
              >
                Delete folder and files
              </Button>
            </div>
            {folderGate && (
              <div className="mt-3 space-y-2">
                <p className="text-xs text-ink-muted">
                  Type the folder name exactly to confirm deletion. Files attached to agents
                  block the deletion until detached. This cannot be undone.
                </p>
                <input
                  autoFocus
                  value={typedName}
                  onChange={(event) => setTypedName(event.target.value)}
                  placeholder={folderDialog.name}
                  className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={busy || !destructiveReady}
                  onClick={removeFolderForced}
                >
                  Delete permanently
                </Button>
              </div>
            )}
            <div className="mt-3 flex justify-end">
              <Button variant="ghost" size="sm" onClick={closeFolderDialog}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
