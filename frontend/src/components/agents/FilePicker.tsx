import { useEffect, useRef, useState } from 'react'
import type { AgentFolderRule } from '../../api/agents'
import { axiosDetail } from '../../api/client'
import { listDocuments, listFolders, type FileItem, type Folder } from '../../api/files'
import Button from '../ui/Button'

export interface FileSelection {
  folders: AgentFolderRule[]
  documents: string[]
}

interface FilePickerProps {
  workspaceId: string
  value: FileSelection
  onChange: (value: FileSelection) => void
  onSummary?: (total: number) => void
  open: boolean
  onClose: () => void
}

/** React cannot set `indeterminate` through props, so it goes on the element. */
function FolderBox({
  checked,
  indeterminate,
  onChange,
}: {
  checked: boolean
  indeterminate: boolean
  onChange: () => void
}) {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate
  })
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      className="accent-primary"
    />
  )
}

export default function FilePicker({
  workspaceId,
  value,
  onChange,
  onSummary,
  open,
  onClose,
}: FilePickerProps) {
  const [folders, setFolders] = useState<Folder[]>([])
  const [unfiled, setUnfiled] = useState<FileItem[]>([])
  const [inFolder, setInFolder] = useState<Map<string, FileItem[]>>(new Map())
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // `value` is read only when the picker opens; a ref keeps it out of the effect's
  // dependencies, because every edit rewrites `value` through the parent form.
  const valueRef = useRef(value)
  valueRef.current = value
  const runRef = useRef(0)

  useEffect(() => {
    if (!open) return
    const run = ++runRef.current
    setLoading(true)
    setError(null)
    setExpanded(new Set())
    void Promise.all([listFolders(workspaceId), listDocuments(workspaceId)])
      .then(([folderList, docList]) => {
        if (run !== runRef.current) return
        const grouped = new Map<string, FileItem[]>()
        const unfiledDocs: FileItem[] = []
        for (const doc of docList.documents) {
          if (doc.folder_id) {
            const list = grouped.get(doc.folder_id) ?? []
            list.push(doc)
            grouped.set(doc.folder_id, list)
          } else {
            unfiledDocs.push(doc)
          }
        }
        setFolders(folderList)
        setInFolder(grouped)
        setUnfiled(unfiledDocs)

        // Seed the checked set from the write-time rules, then edit freely in
        // check-space: the outgoing rules are re-derived from what is checked.
        const initial = new Set<string>()
        for (const rule of valueRef.current.folders) {
          for (const file of grouped.get(rule.id) ?? []) {
            if (!rule.exclude_document_ids.includes(file.id)) initial.add(file.id)
          }
        }
        for (const doc of unfiledDocs) {
          if (valueRef.current.documents.includes(doc.id)) initial.add(doc.id)
        }
        setChecked(initial)
        setLoading(false)
      })
      .catch((caught) => {
        if (run !== runRef.current) return
        setError(axiosDetail(caught) ?? 'Could not load the workspace files.')
        setLoading(false)
      })
  }, [open, workspaceId])

  useEffect(() => {
    if (!open) return
    onSummary?.(checked.size)
  }, [open, checked, onSummary])

  const recheck = (next: Set<string>) => {
    setChecked(next)
    const folderRules: AgentFolderRule[] = []
    for (const [folderId, files] of inFolder) {
      if (!files.some((file) => next.has(file.id))) continue
      folderRules.push({
        id: folderId,
        exclude_document_ids: files.filter((file) => !next.has(file.id)).map((file) => file.id),
      })
    }
    onChange({ folders: folderRules, documents: unfiled.filter((file) => next.has(file.id)).map((file) => file.id) })
  }

  const toggleFile = (id: string) => {
    const next = new Set(checked)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    recheck(next)
  }

  const toggleFolder = (files: FileItem[]) => {
    const allChecked = files.length > 0 && files.every((file) => checked.has(file.id))
    const next = new Set(checked)
    for (const file of files) {
      if (allChecked) next.delete(file.id)
      else next.add(file.id)
    }
    recheck(next)
  }

  const toggleExpanded = (folderId: string) =>
    setExpanded((previous) => {
      const next = new Set(previous)
      if (next.has(folderId)) next.delete(folderId)
      else next.add(folderId)
      return next
    })

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex bg-black/40 p-2 sm:p-4 dark:bg-black/60">
      <div className="m-auto flex max-h-full w-full max-w-md flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-drawer animate-scale-in">
        <header className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2 className="text-[15px] font-semibold text-ink">Attach files</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1 text-ink-subtle hover:text-ink hover:bg-surface-muted transition-colors"
          >
            ✕
          </button>
        </header>
        <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4 text-[13px] text-ink">
          {loading && <p className="text-ink-muted">Loading files…</p>}
          {error && <p className="text-status-error">{error}</p>}
          {!loading && !error && (
            <>
              {folders.map((folder) => {
                const files = inFolder.get(folder.id) ?? []
                const checkedCount = files.filter((file) => checked.has(file.id)).length
                const isOpen = expanded.has(folder.id)
                return (
                  <div
                    key={folder.id}
                    className="rounded-lg border border-line p-2.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <FolderBox
                          checked={files.length > 0 && checkedCount === files.length}
                          indeterminate={checkedCount > 0 && checkedCount < files.length}
                          onChange={() => toggleFolder(files)}
                        />
                        <button
                          type="button"
                          onClick={() => toggleExpanded(folder.id)}
                          className="text-[13px] font-medium text-ink"
                        >
                          {isOpen ? '▾' : '▸'} {folder.name}
                        </button>
                      </div>
                      <span className="font-mono text-[11px] text-ink-subtle">
                        {checkedCount} of {files.length} files
                      </span>
                    </div>
                    {isOpen && (
                      <div className="mt-1.5 space-y-1.5 border-l border-line pl-3">
                        {files.map((file) => (
                          <label key={file.id} className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={checked.has(file.id)}
                              onChange={() => toggleFile(file.id)}
                              className="accent-primary"
                            />
                            <span>{file.filename ?? 'Untitled file'}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
              {unfiled.length > 0 && (
                <div className="rounded-lg border border-line p-2.5">
                  <h3 className="mb-1.5 text-[13px] font-medium text-ink">Unfiled</h3>
                  {unfiled.map((file) => (
                    <label key={file.id} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={checked.has(file.id)}
                        onChange={() => toggleFile(file.id)}
                        className="accent-primary"
                      />
                      <span>{file.filename ?? 'Untitled file'}</span>
                    </label>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
        <footer className="flex items-center justify-end gap-2 border-t border-line px-5 py-3">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" onClick={onClose}>
            Done
          </Button>
        </footer>
      </div>
    </div>
  )
}
