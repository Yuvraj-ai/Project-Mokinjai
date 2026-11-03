import { useEffect, useState } from 'react'
import { BookOpen, Plus, Trash2 } from 'lucide-react'
import { listWorkspaces } from '../api/workspaces'
import {
  SKILL_DESCRIPTION_MAX,
  SKILL_NAME_PATTERN,
  createSkill,
  deleteSkill,
  getReferenceMenu,
  listSkills,
  updateSkill,
  type ReferenceMenu,
  type Skill,
  type SkillInput,
} from '../api/skills'
import SkillEditor from '../components/skills/SkillEditor'
import Button from '../components/ui/Button'
import { Spinner } from '../components/ui/Feedback'
import { cn } from '../lib/utils'

function axiosError(error: unknown): { status: number | null; detail: string | null } {
  if (!error || typeof error !== 'object' || !('response' in error)) {
    return { status: null, detail: null }
  }
  const response = (error as { response?: { status?: number; data?: { detail?: unknown } } })
    .response
  const detail = response?.data?.detail
  return {
    status: response?.status ?? null,
    detail: typeof detail === 'string' ? detail : null,
  }
}

interface EditorState {
  id: string | null
  originalName: string
  name: string
  description: string
  content: string
  referencedBy: string[]
  skillRefs: string[]
  toolRefs: string[]
}

const emptyMenu: ReferenceMenu = { skills: [], tools: [] }

export default function SkillsPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [skills, setSkills] = useState<Skill[]>([])
  const [menu, setMenu] = useState<ReferenceMenu>(emptyMenu)
  const [loading, setLoading] = useState(true)
  const [editor, setEditor] = useState<EditorState | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [banner, setBanner] = useState<string | null>(null)

  useEffect(() => {
    listWorkspaces()
      .then(async (workspaces) => {
        if (!workspaces?.length) return
        const id = workspaces[0].id
        setWorkspaceId(id)
        setSkills(await listSkills(id))
        setMenu(await getReferenceMenu(id))
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
      content: '',
      referencedBy: [],
      skillRefs: [],
      toolRefs: [],
    })
    setError(null)
    setBanner(null)
  }

  const openExisting = (skill: Skill) => {
    setEditor({
      id: skill.id,
      originalName: skill.name,
      name: skill.name,
      description: skill.description,
      content: skill.content,
      referencedBy: skill.referenced_by,
      skillRefs: skill.skill_refs,
      toolRefs: skill.tool_refs,
    })
    setError(null)
    setBanner(null)
  }

  const refresh = async (id: string) => {
    setSkills(await listSkills(id))
    setMenu(await getReferenceMenu(id))
  }

  const save = async () => {
    if (!workspaceId || !editor) return
    if (!SKILL_NAME_PATTERN.test(editor.name)) {
      setError('A skill name starts with a letter and uses only letters, digits and underscores.')
      return
    }
    const payload: SkillInput = {
      name: editor.name,
      description: editor.description,
      content: editor.content,
    }
    const wasUpdate = editor.id !== null
    const previousName = editor.originalName

    setSaving(true)
    setError(null)
    setBanner(null)
    try {
      const saved = wasUpdate
        ? await updateSkill(workspaceId, editor.id as string, payload)
        : await createSkill(workspaceId, payload)
      openExisting(saved)
      await refresh(workspaceId)
      if (wasUpdate && previousName !== saved.name) {
        setBanner(
          `Renamed. References to @${previousName} were updated. Agents already built keep their old content until rebuilt.`
        )
      }
    } catch (caught) {
      const { status, detail } = axiosError(caught)
      if (status === 409) {
        setBanner(detail ?? 'A skill with that name already exists.')
      } else {
        setError(detail ?? 'Could not save this skill.')
      }
    } finally {
      setSaving(false)
    }
  }

  const remove = async (skill: Skill) => {
    if (!workspaceId) return
    setError(null)
    setBanner(null)
    try {
      await deleteSkill(workspaceId, skill.id)
      await refresh(workspaceId)
      if (editor?.id === skill.id) setEditor(null)
    } catch (caught) {
      setBanner(axiosError(caught).detail ?? 'Could not delete this skill.')
    }
  }

  if (loading || !workspaceId) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    )
  }

  const labelClass = 'mb-1.5 block text-[13px] font-medium text-ink'
  const inputClass =
    'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring'

  return (
    <div className="flex h-full">
      <aside className="w-72 shrink-0 border-r border-line bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <h1 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <BookOpen className="h-4 w-4" aria-hidden /> Skills
          </h1>
          <Button size="sm" onClick={openNew}>
            <Plus className="h-3.5 w-3.5" aria-hidden /> New
          </Button>
        </div>

        {banner && (
          <p className="mb-3 rounded-lg bg-surface-muted px-2.5 py-1.5 text-xs text-ink-muted">
            {banner}
          </p>
        )}

        <ul className="space-y-0.5">
          {skills.map((skill) => (
            <li key={skill.id} className="group flex items-center gap-1">
              <button
                type="button"
                onClick={() => openExisting(skill)}
                className={cn(
                  'flex-1 rounded-lg px-2 py-1.5 text-left text-[13px] transition-colors duration-150',
                  editor?.id === skill.id
                    ? 'bg-surface-muted text-ink'
                    : 'text-ink-muted hover:bg-surface-muted hover:text-ink',
                )}
              >
                <span className="font-mono">@{skill.name}</span>
                <span className="mt-0.5 block truncate text-[11px] text-ink-subtle">
                  {skill.description}
                </span>
              </button>
              <button
                type="button"
                onClick={() => remove(skill)}
                title="Delete skill"
                aria-label={`Delete ${skill.name}`}
                className="rounded p-1 text-ink-subtle opacity-0 transition-opacity group-hover:opacity-100 hover:bg-status-error-soft hover:text-status-error"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
          {skills.length === 0 && (
            <li className="px-2 text-xs text-ink-subtle">
              No skills yet. Create one, then attach it to an agent.
            </li>
          )}
        </ul>
      </aside>

      <section className="flex-1 overflow-y-auto p-6">
        {!editor ? (
          <p className="text-sm text-ink-subtle">Select a skill, or create a new one.</p>
        ) : (
          <div className="mx-auto max-w-3xl space-y-5">
            <label className="block">
              <span className={labelClass}>Name</span>
              <input
                value={editor.name}
                onChange={(event) => setEditor({ ...editor, name: event.target.value })}
                placeholder="Writer"
                className={inputClass + ' font-mono'}
              />
              <span className="mt-1 block text-xs text-ink-subtle">
                Referenced as <code className="font-mono">@{editor.name || 'Name'}</code>
              </span>
            </label>

            <label className="block">
              <span className={labelClass}>Description — the line the model sees at startup</span>
              <input
                value={editor.description}
                maxLength={SKILL_DESCRIPTION_MAX}
                onChange={(event) => setEditor({ ...editor, description: event.target.value })}
                placeholder="Sets the tone and voice for the agent."
                className={inputClass}
              />
              <span className="mt-1 block font-mono text-[11px] text-ink-subtle">
                - {editor.name || 'Name'}: {editor.description || '…'}
              </span>
            </label>

            <div>
              <span className={labelClass}>Instructions</span>
              <SkillEditor
                content={editor.content}
                menu={menu}
                onChange={(content) => setEditor({ ...editor, content })}
              />
            </div>

            {editor.referencedBy.length > 0 && (
              <p className="rounded-lg bg-surface-muted border border-line px-3 py-2 text-xs text-ink-muted">
                Referenced by {editor.referencedBy.join(', ')}. Changes won&apos;t affect existing
                agents until rebuilt.
              </p>
            )}

            {error && (
              <p className="rounded-lg bg-status-error-soft px-3 py-2 text-[13px] text-status-error">
                {error}
              </p>
            )}

            <div className="flex items-center gap-3">
              <Button onClick={save} loading={saving}>
                {saving ? 'Saving…' : 'Save'}
              </Button>
              <span className="font-mono text-xs text-ink-subtle">
                {editor.skillRefs.length} skill ref{editor.skillRefs.length === 1 ? '' : 's'},{' '}
                {editor.toolRefs.length} tool ref{editor.toolRefs.length === 1 ? '' : 's'}
              </span>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
