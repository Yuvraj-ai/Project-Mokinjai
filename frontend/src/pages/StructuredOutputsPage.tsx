import { useEffect, useState } from 'react'
import { Braces, Loader2, Plus, Trash2 } from 'lucide-react'
import { listWorkspaces } from '../api/workspaces'
import {
  createStructuredOutput,
  deleteStructuredOutput,
  fieldTypeLabel,
  getStructuredOutput,
  listStructuredOutputs,
  parseSchema,
  updateStructuredOutput,
  type OutputField,
  type StructuredOutput,
} from '../api/structuredOutputs'
import FieldList from '../components/structured-output/FieldList'
import FieldDetail from '../components/structured-output/FieldDetail'
import SchemaPreview from '../components/structured-output/SchemaPreview'
import PasteSchema from '../components/structured-output/PasteSchema'
import Button from '../components/ui/Button'
import { Spinner, EmptyState } from '../components/ui/Feedback'
import { cn } from '../lib/utils'

const newField = (): OutputField => ({
  name: '',
  type: 'string',
  description: '',
  required: true,
})

interface EditorState {
  id: string | null
  originalName: string
  name: string
  description: string
  fields: OutputField[]
  selected: number | null
  referencedBy: string[]
}

export default function StructuredOutputsPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [outputs, setOutputs] = useState<StructuredOutput[]>([])
  const [loading, setLoading] = useState(true)
  const [editor, setEditor] = useState<EditorState | null>(null)
  const [mode, setMode] = useState<'builder' | 'paste'>('builder')
  const [compiled, setCompiled] = useState<Record<string, unknown> | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [banner, setBanner] = useState<string | null>(null)

  useEffect(() => {
    listWorkspaces()
      .then(async (workspaces) => {
        if (!workspaces?.length) return
        const id = workspaces[0].id
        setWorkspaceId(id)
        setOutputs(await listStructuredOutputs(id))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const openNew = () => {
    setEditor({
      id: null,
      originalName: '',
      name: '',
      description: '',
      fields: [newField()],
      selected: 0,
      referencedBy: [],
    })
    setCompiled(null)
    setError(null)
    setBanner(null)
    setMode('builder')
  }

  const openExisting = async (output: StructuredOutput) => {
    setEditor({
      id: output.id,
      originalName: output.name,
      name: output.name,
      description: output.description,
      fields: output.fields,
      selected: output.fields.length ? 0 : null,
      referencedBy: output.referenced_by,
    })
    setCompiled(output.compiled_schema)
    setError(null)
    setBanner(null)
    setMode('builder')
    if (!workspaceId) return
    try {
      const detail = await getStructuredOutput(workspaceId, output.id)
      setCompiled(detail.compiled_schema)
    } catch {
      // The list copy is enough to edit from.
    }
  }

  const patchField = (index: number, patch: Partial<OutputField>) => {
    setEditor((current) => {
      if (!current) return current
      const fields = [...current.fields]
      fields[index] = { ...fields[index], ...patch }
      return { ...current, fields }
    })
  }

  const reorder = (from: number, to: number) => {
    setEditor((current) => {
      if (!current) return current
      const fields = [...current.fields]
      const [moved] = fields.splice(from, 1)
      fields.splice(to, 0, moved)
      return { ...current, fields, selected: to }
    })
  }

  const handleSave = async () => {
    if (!workspaceId || !editor) return
    setSaving(true)
    setError(null)
    try {
      const payload = { name: editor.name.trim(), description: editor.description.trim(), fields: editor.fields }
      const saved = editor.id
        ? await updateStructuredOutput(workspaceId, editor.id, payload)
        : await createStructuredOutput(workspaceId, payload)
      setOutputs(await listStructuredOutputs(workspaceId))
      setCompiled(saved.compiled_schema)
      setEditor((current) =>
        current
          ? { ...current, id: saved.id, originalName: saved.name, referencedBy: saved.referenced_by }
          : current
      )
    } catch (caught: unknown) {
      setError((caught as { message?: string })?.message || 'Could not save this output')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (output: StructuredOutput) => {
    if (!workspaceId) return
    setBanner(null)
    setError(null)
    try {
      await deleteStructuredOutput(workspaceId, output.id)
      setOutputs((current) => current.filter((item) => item.id !== output.id))
      if (editor?.id === output.id) setEditor(null)
    } catch (caught: unknown) {
      setBanner((caught as { message?: string })?.message || 'Could not delete this output')
    }
  }

  if (loading || !workspaceId) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner className="w-6 h-6" />
      </div>
    )
  }

  const otherDefinitions = outputs
    .filter((output) => output.id !== editor?.id)
    .map((output) => ({ name: output.name, fieldCount: output.fields.length }))

  const renaming = editor && editor.name.trim() !== editor.originalName ? editor.originalName : null
  return (
    <div className="max-w-6xl mx-auto px-8 py-10">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-ink tracking-tight leading-tight">Structured Output</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Shapes agents can be asked to return. Referenced by name, e.g.{' '}
            <span className="font-mono">@Step</span>.
          </p>
        </div>
        <Button onClick={openNew}>
          <Plus className="w-4 h-4" aria-hidden /> New output
        </Button>
      </div>

      {banner && (
        <p className="mb-6 rounded-lg bg-surface-muted border border-line px-3 py-2 text-xs text-ink-muted">
          {banner}
        </p>
      )}

      {editor && (
        <div className="mb-8 rounded-xl border border-line bg-surface p-5">
          <div className="flex items-end justify-between gap-4 mb-4">
            <div className="min-w-0">
              <div className="text-lg font-semibold text-ink truncate">
                {editor.name.trim() || 'New output'}
              </div>
              {editor.referencedBy.length > 0 && (
                <div className="mt-1 text-xs text-ink-muted">
                  Referenced by {editor.referencedBy.join(', ')}. Changes won&apos;t affect existing agents
                  until rebuilt.
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <div className="flex rounded-lg border border-line overflow-hidden">
                {(['builder', 'paste'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setMode(tab)}
                    className={cn(
                      'px-3 py-1.5 text-[13px] transition-colors duration-150',
                      mode === tab
                        ? 'bg-surface-muted text-ink'
                        : 'text-ink-subtle hover:text-ink',
                    )}
                  >
                    {tab === 'builder' ? 'Builder' : 'Paste JSON Schema'}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setEditor(null)}
                className="rounded-lg border border-line px-3 py-1.5 text-[13px] text-ink-muted hover:bg-surface-muted transition-colors"
              >
                Close
              </button>
              <button
                onClick={() => void handleSave()}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-1.5 text-[13px] font-medium text-ink hover:bg-surface-muted transition-colors disabled:opacity-50"
              >
                {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />} Save
              </button>
            </div>
          </div>

          {renaming && (
            <p className="mb-4 rounded-lg bg-surface-muted border border-line px-3 py-2 text-xs text-ink-muted">
              Renaming {renaming} updates every output that references it.
            </p>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-[1fr_2fr] gap-4 mb-4">
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-ink">Name</span>
              <input
                value={editor.name}
                onChange={(event) => setEditor({ ...editor, name: event.target.value })}
                placeholder="MathReasoning"
                className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm font-mono text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-ink">Description</span>
              <input
                value={editor.description}
                onChange={(event) => setEditor({ ...editor, description: event.target.value })}
                placeholder="Reasoning steps with units, then the final answer."
                className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
          </div>

          {mode === 'paste' ? (
            <PasteSchema
              onParse={(raw) => parseSchema(workspaceId, raw)}
              onUse={(parsed) => {
                setEditor((current) =>
                  current
                    ? {
                        ...current,
                        fields: parsed.fields.length ? parsed.fields : current.fields,
                        name: current.name.trim() ? current.name : parsed.title ?? '',
                        description: current.description.trim() ? current.description : parsed.description ?? '',
                        selected: 0,
                      }
                    : current
                )
                setMode('builder')
              }}
            />
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-[250px_1fr] gap-4">
              <FieldList
                fields={editor.fields}
                selectedIndex={editor.selected}
                onSelect={(index) => setEditor({ ...editor, selected: index })}
                onReorder={reorder}
                onAdd={() =>
                  setEditor({
                    ...editor,
                    fields: [...editor.fields, newField()],
                    selected: editor.fields.length,
                  })
                }
              />

              {editor.selected !== null && editor.fields[editor.selected] ? (
                <FieldDetail
                  field={editor.fields[editor.selected]}
                  definitions={otherDefinitions}
                  onChange={(patch) => patchField(editor.selected as number, patch)}
                  onRemove={() => {
                    const fields = editor.fields.filter((_, index) => index !== editor.selected)
                    setEditor({
                      ...editor,
                      fields,
                      selected: fields.length ? Math.max(0, (editor.selected as number) - 1) : null,
                    })
                  }}
                />
              ) : (
                <div className="rounded-lg border border-dashed border-line p-8 text-center text-xs text-ink-muted">
                  Select a field to edit it, or add one.
                </div>
              )}
            </div>
          )}

          {error && <p className="mt-3 text-xs text-status-error whitespace-pre-wrap">{error}</p>}

          <div className="mt-4">
            <SchemaPreview schema={compiled} />
          </div>
        </div>
      )}

      {outputs.length === 0 ? (
        <div className="bg-surface border border-line rounded-xl">
          <EmptyState
            icon={Braces}
            title="No output shapes yet"
            description="Define the JSON shape an agent should return, by hand or by pasting a schema."
          />
        </div>
      ) : (
        <div className="space-y-3">
          {outputs.map((output) => {
            const blocked = output.referenced_by.length > 0
            const refs = Array.from(
              new Set(
                output.fields
                  .flatMap((field) => [field.ref, field.items_ref])
                  .filter((value): value is string => Boolean(value))
              )
            )
            return (
              <div
                key={output.id}
                className="bg-surface rounded-xl border border-line p-4 flex items-start justify-between gap-3"
              >
                <button onClick={() => void openExisting(output)} className="text-left min-w-0">
                  <div className="text-sm font-medium text-ink">{output.name}</div>
                  {output.description && (
                    <div className="text-xs text-ink-muted mt-1">{output.description}</div>
                  )}
                  <div className="flex flex-wrap items-center gap-1.5 mt-2">
                    <span className="rounded-md border border-line bg-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
                      {output.fields.length} fields
                    </span>
                    {refs.length > 0 && (
                      <span className="rounded-md border border-line bg-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
                        refs {refs.map((ref) => `@${ref}`).join(', ')}
                      </span>
                    )}
                    {blocked && (
                      <span className="rounded-md border border-line bg-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
                        referenced by {output.referenced_by.length}
                      </span>
                    )}
                    {output.fields.length > 0 && (
                      <span className="font-mono text-xs text-ink-muted">
                        {output.fields.map((field) => `${field.name}:${fieldTypeLabel(field)}`).join(' · ')}
                      </span>
                    )}
                  </div>
                </button>
                <button
                  onClick={() => void handleDelete(output)}
                  disabled={blocked}
                  title={
                    blocked
                      ? `Cannot delete: referenced by ${output.referenced_by.join(', ')}. Remove the reference first.`
                      : 'Delete'
                  }
                  className={cn(
                    'shrink-0 rounded-md p-1.5 transition-colors',
                    blocked
                      ? 'text-ink-subtle opacity-50 cursor-not-allowed'
                      : 'text-ink-subtle hover:bg-status-error-soft hover:text-status-error',
                  )}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
