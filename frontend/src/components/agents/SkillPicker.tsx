import { Lock } from 'lucide-react'
import type { AgentOption } from '../../api/agents'
import MultiSelect from './MultiSelect'
import { cn } from '../../lib/utils'

export interface SkillClosure {
  skills: { id: string; name: string; root: boolean }[]
  tools: string[]
}

/**
 * The picker's preview of what the server will resolve. The saved agent's own
 * `resolved` block stays authoritative; this only keeps the form honest while
 * the user is still choosing.
 */
export function resolvePreview(skills: AgentOption[], selectedIds: string[]): SkillClosure {
  const byName = new Map<string, AgentOption>()
  for (const skill of skills) byName.set(skill.name.toLowerCase(), skill)

  const selected = skills.filter((skill) => selectedIds.includes(skill.id))
  const roots = new Set(selected.map((skill) => skill.name.toLowerCase()))
  const seen = new Set<string>()
  const closure: { id: string; name: string; root: boolean }[] = []
  const tools = new Set<string>()
  const queue = [...selected]

  while (queue.length > 0) {
    const skill = queue.shift() as AgentOption
    const key = skill.name.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    closure.push({ id: skill.id, name: skill.name, root: roots.has(key) })
    for (const tool of skill.tool_refs ?? []) tools.add(tool.toLowerCase())
    for (const ref of skill.skill_refs ?? []) {
      const next = byName.get(ref.toLowerCase())
      if (next) queue.push(next)
    }
  }

  return { skills: closure, tools: [...tools] }
}

interface SkillPickerProps {
  skills: AgentOption[]
  tools: AgentOption[]
  skillIds: string[]
  toolIds: string[]
  onSkillsChange: (ids: string[]) => void
  onToolsChange: (ids: string[]) => void
  skillError?: string
  toolError?: string
}

export default function SkillPicker({
  skills,
  tools,
  skillIds,
  toolIds,
  onSkillsChange,
  onToolsChange,
  skillError,
  toolError,
}: SkillPickerProps) {
  const closure = resolvePreview(skills, skillIds)
  const required = new Set(closure.tools)
  const direct = tools.filter((tool) => toolIds.includes(tool.id))

  const effective = new Map<string, { name: string; source: string; locked: boolean }>()
  for (const name of closure.tools) {
    effective.set(name, { name, source: 'skill', locked: true })
  }
  for (const tool of direct) {
    effective.set(tool.name.toLowerCase(), {
      name: tool.name,
      source: 'workspace',
      locked: required.has(tool.name.toLowerCase()),
    })
  }

  return (
    <div className="space-y-4">
      <MultiSelect
        label="Skills"
        options={skills}
        values={skillIds}
        onChange={onSkillsChange}
        emptyText="No skills yet."
        error={skillError}
      />

      {closure.skills.length > 0 && (
        <div>
          <span className="mb-1.5 block text-[13px] font-medium text-ink">
            Resolved skills
          </span>
          <div className="flex flex-wrap gap-1.5">
            {closure.skills.map((skill) => (
              <span
                key={skill.id || skill.name}
                className="inline-flex items-center rounded-full border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-ink-muted"
              >
                @{skill.name}
                {!skill.root && <span className="ml-1 normal-case text-ink-subtle">nested</span>}
              </span>
            ))}
          </div>
        </div>
      )}

      <div>
        <span className="mb-1.5 block text-[13px] font-medium text-ink">
          Tools the model can call
        </span>
        <div className="mb-2 flex flex-wrap gap-1.5">
          {[...effective.values()].map((tool) => (
            <span
              key={tool.name}
              className={cn(
                'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide',
                tool.locked
                  ? 'border-line-strong bg-surface-muted text-ink'
                  : 'border-line bg-surface text-ink-muted',
              )}
              title={tool.locked ? 'Required by a selected skill' : `From the ${tool.source} tool set`}
            >
              {tool.locked && <Lock className="h-2.5 w-2.5" aria-hidden />}
              <span>{tool.name}</span>
            </span>
          ))}
          {effective.size === 0 && (
            <span className="text-xs text-ink-subtle">No tools resolved yet.</span>
          )}
        </div>
        <MultiSelect
          label="Add tools"
          options={tools}
          values={toolIds}
          onChange={onToolsChange}
          emptyText="No workspace tools yet."
          error={toolError}
        />
      </div>
    </div>
  )
}
