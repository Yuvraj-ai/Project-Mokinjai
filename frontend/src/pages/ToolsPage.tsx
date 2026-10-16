import { useEffect, useState } from 'react'
import { Loader2, Plus, Trash2, Wrench } from 'lucide-react'
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
        <Loader2 className="w-5 h-5 text-accent animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-8 py-10">
      <div className="flex items-end justify-between mb-8">
        <div>
          <h1 className="text-3xl font-display text-ink-900 dark:text-cream-100 tracking-tight leading-none">
            Tools
          </h1>
          <p className="text-ink-400 dark:text-ink-300 mt-2 text-sm font-body">
            Built-in tools the platform runs itself, and Python functions you write for agents to
            call.
          </p>
        </div>
        <button
          onClick={() => {
            setCreating(true)
            setEditing(null)
          }}
          className="inline-flex items-center gap-2 bg-ink-800 dark:bg-cream-200 hover:bg-ink-900 dark:hover:bg-cream-300 text-cream-50 dark:text-ink-800 font-body font-medium py-2 px-5 rounded-lg text-sm"
        >
          <Plus className="w-4 h-4" /> New tool
        </button>
      </div>

      {banner && (
        <div className="mb-4 rounded-lg border border-status-error/40 bg-status-error/5 px-4 py-2.5 text-sm font-body text-status-error">
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
        <h2 className="text-[11px] uppercase tracking-wider font-semibold text-ink-400 mb-3">
          Built-in ({builtins.length})
        </h2>
        <div className="space-y-2">
          {builtins.map((builtin) => (
            <div
              key={builtin.built_in_key}
              className="rounded-xl border border-ink-100/60 dark:border-ink-700/60 bg-white dark:bg-ink-800 p-4"
            >
              <div className="flex items-center gap-2">
                <span className="font-body font-medium text-ink-900 dark:text-cream-100">
                  {builtin.name}
                </span>
                <span className="rounded bg-ink-50 dark:bg-ink-700 px-1.5 py-0.5 text-[10px] text-ink-500 dark:text-ink-200">
                  Built-in
                </span>
                <span className="text-[10px] font-mono text-ink-300">{builtin.built_in_key}</span>
              </div>
              <div className="text-xs text-ink-400 mt-1">{builtin.description}</div>
            </div>
          ))}
          {builtins.length === 0 && (
            <p className="text-sm font-body text-ink-400">No built-in tools are registered.</p>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-[11px] uppercase tracking-wider font-semibold text-ink-400 mb-3">
          Custom ({tools.length})
        </h2>
        {tools.length === 0 ? (
          <div className="text-center py-16">
            <Wrench
              className="w-10 h-10 text-cream-300 dark:text-ink-600 mx-auto mb-4"
              strokeWidth={1.5}
            />
            <h3 className="text-2xl font-display italic text-ink-900 dark:text-cream-100 mb-2">
              No custom tools yet
            </h3>
            <p className="text-sm text-ink-400 dark:text-ink-300 font-body">
              Write a Python function with a docstring and a type hint on every parameter — the
              schema comes out of it.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {tools.map((tool) => (
              <div
                key={tool.id}
                className="flex items-start justify-between gap-3 rounded-xl border border-ink-100/60 dark:border-ink-700/60 bg-white dark:bg-ink-800 p-4"
              >
                <button
                  onClick={() => {
                    setCreating(false)
                    setEditing(tool)
                  }}
                  className="text-left min-w-0"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-body font-medium text-ink-900 dark:text-cream-100">
                      {tool.name}
                    </span>
                    <span className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent">
                      Custom
                    </span>
                  </div>
                  <div className="text-xs text-ink-400 mt-1">{tool.description}</div>
                  <div className="flex flex-wrap items-center gap-1.5 mt-2">
                    <span className="rounded bg-ink-50 dark:bg-ink-700 px-1.5 py-0.5 text-[10px] text-ink-500 dark:text-ink-200">
                      {tool.parameters.length} params
                    </span>
                    <span className="rounded bg-ink-50 dark:bg-ink-700 px-1.5 py-0.5 text-[10px] text-ink-500 dark:text-ink-200">
                      needs sandbox
                    </span>
                    <span className="text-[10px] font-mono text-ink-300">
                      {tool.parameters
                        .map((parameter) => `${parameter.name}:${parameterTypeLabel(parameter)}`)
                        .join(' · ')}
                    </span>
                  </div>
                </button>
                <button
                  onClick={() => void handleDelete(tool)}
                  title="Delete"
                  className="shrink-0 text-ink-300 hover:text-status-error"
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
