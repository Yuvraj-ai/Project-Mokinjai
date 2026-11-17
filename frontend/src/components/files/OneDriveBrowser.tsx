import { useCallback, useEffect, useState } from 'react'
import { ChevronLeft, Folder as FolderIcon, Loader2 } from 'lucide-react'
import { axiosDetail } from '../../api/client'
import {
  getConnectionStatus,
  getOneDriveAuthUrl,
  importOneDriveItem,
  listOneDriveItems,
  type OneDriveItem,
} from '../../api/cloudImports'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

interface OneDriveBrowserProps {
  open: boolean
  workspaceId: string
  onClose: () => void
  onImported: () => void
}

interface Crumb {
  id: string
  name: string
}

export default function OneDriveBrowser({ open, workspaceId, onClose, onImported }: OneDriveBrowserProps) {
  const [connected, setConnected] = useState<boolean | null>(null)
  const [trail, setTrail] = useState<Crumb[]>([])
  const [items, setItems] = useState<OneDriveItem[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fileErrors, setFileErrors] = useState<string[]>([])

  const current = trail[trail.length - 1]

  const load = useCallback(
    async (folderId?: string) => {
      setLoading(true)
      setError(null)
      try {
        setItems(await listOneDriveItems(folderId))
      } catch (caught) {
        setError(axiosDetail(caught) ?? 'Could not load OneDrive')
      } finally {
        setLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    if (!open) return
    setTrail([])
    setSelected(new Set())
    setFileErrors([])
    void (async () => {
      try {
        const connections = await getConnectionStatus()
        const hasOneDrive = connections.some((connection) => connection.provider === 'onedrive')
        setConnected(hasOneDrive)
        if (hasOneDrive) await load()
      } catch (caught) {
        setConnected(false)
        setError(axiosDetail(caught) ?? 'Could not check the OneDrive connection')
      }
    })()
  }, [open, load])

  async function connect() {
    try {
      window.location.href = await getOneDriveAuthUrl()
    } catch (caught) {
      setError(axiosDetail(caught) ?? 'Could not start the OneDrive connection')
    }
  }

  function openFolder(item: OneDriveItem) {
    setTrail((currentTrail) => [...currentTrail, { id: item.id, name: item.name }])
    void load(item.id)
  }

  function goBack() {
    const next = trail.slice(0, -1)
    setTrail(next)
    void load(next[next.length - 1]?.id)
  }

  async function importSelected() {
    setImporting(true)
    setFileErrors([])
    const failures: string[] = []
    for (const item of items.filter((entry) => selected.has(entry.id))) {
      try {
        await importOneDriveItem(workspaceId, item.id)
      } catch (caught) {
        failures.push(`${item.name}: ${axiosDetail(caught) ?? 'import failed'}`)
      }
    }
    setImporting(false)
    setFileErrors(failures)
    if (failures.length === 0) onImported()
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Import from OneDrive"
      description="Files become workspace files; every member of this workspace can read them."
      width="lg"
      footer={
        connected ? (
          <>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              onClick={() => void importSelected()}
              loading={importing}
              disabled={selected.size === 0}
            >
              Import {selected.size || ''} file{selected.size === 1 ? '' : 's'}
            </Button>
          </>
        ) : undefined
      }
    >
      {connected === null && (
        <div className="flex items-center gap-2 text-sm text-ink-muted">
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> Checking OneDrive…
        </div>
      )}

      {connected === false && (
        <div className="space-y-3">
          <p className="text-sm text-ink-muted">
            Connect your Microsoft account to browse OneDrive. Only read access is requested.
          </p>
          <Button variant="secondary" onClick={() => void connect()}>
            Connect OneDrive
          </Button>
        </div>
      )}

      {error && (
        <div className="mb-3 rounded-lg bg-status-error-soft px-4 py-3 text-sm text-status-error">
          {error}
        </div>
      )}

      {fileErrors.length > 0 && (
        <div className="mb-3 space-y-1 rounded-lg bg-status-error-soft px-4 py-3 text-sm text-status-error">
          {fileErrors.map((line) => (
            <div key={line}>{line}</div>
          ))}
        </div>
      )}

      {connected && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm">
            {trail.length > 0 && (
              <button
                onClick={goBack}
                className="flex items-center gap-1 text-ink-muted hover:text-ink"
              >
                <ChevronLeft className="w-4 h-4" aria-hidden /> Back
              </button>
            )}
            <span className="font-medium text-ink">
              OneDrive{current ? ` / ${current.name}` : ''}
            </span>
          </div>

          {loading ? (
            <div className="flex items-center gap-2 py-6 text-sm text-ink-muted">
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden /> Loading…
            </div>
          ) : items.length === 0 ? (
            <p className="py-6 text-sm text-ink-subtle">This folder is empty.</p>
          ) : (
            <ul className="divide-y divide-line rounded-lg border border-line">
              {items.map((item) => (
                <li key={item.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                  {item.is_folder ? (
                    <button
                      onClick={() => openFolder(item)}
                      className="flex flex-1 items-center gap-2 text-left text-ink hover:text-primary"
                    >
                      <FolderIcon className="w-4 h-4 text-ink-subtle" aria-hidden />
                      {item.name}
                    </button>
                  ) : (
                    <label className="flex flex-1 items-center gap-2 text-ink">
                      <input
                        type="checkbox"
                        checked={selected.has(item.id)}
                        onChange={(event) =>
                          setSelected((previous) => {
                            const next = new Set(previous)
                            if (event.target.checked) next.add(item.id)
                            else next.delete(item.id)
                            return next
                          })
                        }
                      />
                      {item.name}
                    </label>
                  )}
                  <span className="text-xs text-ink-subtle">
                    {item.is_folder ? `${item.child_count ?? 0} items` : item.mime_type ?? ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Modal>
  )
}
