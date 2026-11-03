import { useEffect, useState } from 'react'
import { Plus, Trash2, Wrench } from 'lucide-react'
import { listWorkspaces } from '../api/workspaces'
import {
  deleteTool,
  listBuiltinTools,
  listTools,
  parameterTypeLabel,
  type BuiltinTool,
  type Tool,
} from '../api/tools'
import { axiosDetail } from '../api/client'
import ToolEditor from '../components/tools/ToolEditor'
import Button from '../components/ui/Button'
import { Spinner, EmptyState } from '../components/ui/Feedback'
import Badge from '../components/ui/Badge'
import { cn } from '../lib/utils'

export default function ToolsPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [tools, setTools] = useState<Tool[]>([])
  const [builtins, setBuiltins] = useState<BuiltinTool[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Tool | null>(null)
  const [creating, setCreating] = useState(false)
  const [banner, setBanner] = useState<string | null>(null)

  useEffect(() => {
    listWorkspaces()
      .then(async (workspaces) => {
        if (!workspaces?.length) return
        const id = workspaces[0].id
        setWorkspaceId(id)
        const [custom, builtin] = await Promise.all([listTools(id), listBuiltinTools(id)])
        setTools(custom)
        setBuiltins(builtin)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleDelete = async (tool: Tool) => {
    if (!workspaceId) return
    setBanner(null)
    try {
      await deleteTool(workspaceId, tool.id)
      setTools((current) => current.filter((item) => item.id !== tool.id))
      if (editing?.id === tool.id) {
        setEditing(null)
        setCreating(false)
      }
    } catch (caught: unknown) {
      setBanner(axiosDetail(caught) || 'Could not delete this tool')
    }
  }

  if (loading || !workspaceId) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner className="w-6 h-6" />
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-8 py-10">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-ink tracking-tight leading-tight">Tools</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Built-in tools the platform runs itself, and Python functions you write for agents to
            call.
          </p>
        </div>
        <Button
          onClick={() => {
            setCreating(true)
            setEditing(null)
          }}
        >
          <Plus className="w-4 h-4" aria-hidden /> New tool
        </Button>
      </div>

      {banner && (
        <div className="mb-4 rounded-lg bg-status-error-soft px-4 py-2.5 text-sm text-status-error">
          {banner}
        </div>
      )}

      {(creating || editing) && (
        <ToolEditor
          // Remount on a different tool: the code box is seeded from the tool it opened.
          key={editing?.id ?? 'new'}
          workspaceId={workspaceId}
          tool={editing}
          onSaved={async (saved) => {
            setCreating(false)
            setEditing(saved)
            setTools(await listTools(workspaceId))
          }}
          onClose={() => {
            setCreating(false)
            setEditing(null)
          }}
        />
      )}

      <section className="mb-10">
        <h2 className="text-[13px] font-semibold text-ink mb-3">
          Built-in <span className="ml-1 font-mono text-xs font-normal text-ink-subtle">{builtins.length}</span>
        </h2>
        <div className="space-y-2">
          {builtins.map((builtin) => (
            <div
              key={builtin.built_in_key}
              className="bg-surface rounded-xl border border-line p-4"
            >
              <div className="flex items-center gap-2.5">
                <span className="text-sm font-medium text-ink">{builtin.name}</span>
                <Badge variant="outline">Built-in</Badge>
                <span className="font-mono text-[11px] text-ink-subtle">{builtin.built_in_key}</span>
              </div>
              <div className="text-[13px] text-ink-muted mt-1">{builtin.description}</div>
            </div>
          ))}
          {builtins.length === 0 && (
            <p className="text-sm text-ink-subtle">No built-in tools are registered.</p>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-[13px] font-semibold text-ink mb-3">
          Custom <span className="ml-1 font-mono text-xs font-normal text-ink-subtle">{tools.length}</span>
        </h2>
        {tools.length === 0 ? (
          <div className="bg-surface border border-line rounded-xl">
            <EmptyState
              icon={Wrench}
              title="No custom tools yet"
              description="Write a Python function with a docstring and a type hint on every parameter — the schema comes out of it."
            />
          </div>
        ) : (
          <div className="space-y-3">
            {tools.map((tool) => (
              <div
                key={tool.id}
                className="flex items-start justify-between gap-3 bg-surface rounded-xl border border-line p-4 transition-colors duration-150 hover:border-line-strong"
              >
                <button
                  onClick={() => {
                    setCreating(false)
                    setEditing(tool)
                  }}
                  className="text-left min-w-0"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm font-medium text-ink">{tool.name}</span>
                    <Badge variant="outline">Custom</Badge>
                  </div>
                  <div className="text-[13px] text-ink-muted mt-1">{tool.description}</div>
                  <div className="flex flex-wrap items-center gap-1.5 mt-2">
                    <span className="rounded-md border border-line bg-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
                      {tool.parameters.length} params
                    </span>
                    <span className="rounded-md border border-line bg-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
                      needs sandbox
                    </span>
                    <span className={cn('font-mono text-[11px] text-ink-subtle')}>
                      {tool.parameters
                        .map((parameter) => `${parameter.name}:${parameterTypeLabel(parameter)}`)
                        .join(' · ')}
                    </span>
                  </div>
                </button>
                <button
                  onClick={() => void handleDelete(tool)}
                  title="Delete"
                  aria-label={`Delete ${tool.name}`}
                  className="shrink-0 rounded-md p-1.5 text-ink-subtle transition-colors hover:bg-status-error-soft hover:text-status-error"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
