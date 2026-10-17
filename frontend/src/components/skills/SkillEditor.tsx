import { useMemo, useRef, useState, type KeyboardEvent } from 'react'
import type { ReferenceMenu } from '../../api/skills'

export interface ActiveReference {
  kind: 'skill' | 'tool'
  query: string
  /** Index of the marker character in the value. */
  start: number
}

/**
 * The reference being typed at `caret`, if any.
 *
 * Mirrors the backend's context rule: a marker only opens a reference when the
 * character before it is the start of the line, whitespace, or one of `([{`.
 * The picker therefore stays shut inside `https://…` and `bob@example.com`.
 * Offering a completion the backend would not recognise is worse than offering
 * none, because the reference would silently not exist.
 */
export function activeReference(value: string, caret: number): ActiveReference | null {
  const lineStart = value.lastIndexOf('\n', caret - 1) + 1
  const before = value.slice(lineStart, caret)
  const match = /(^|[\s([{])([@/])([A-Za-z][A-Za-z0-9_]*)?$/.exec(before)
  if (!match) return null
  return {
    kind: match[2] === '@' ? 'skill' : 'tool',
    query: match[3] ?? '',
    start: lineStart + match.index + match[1].length,
  }
}

interface Props {
  content: string
  menu: ReferenceMenu
  onChange: (content: string) => void
}

export default function SkillEditor({ content, menu, onChange }: Props) {
  const area = useRef<HTMLTextAreaElement | null>(null)
  const [active, setActive] = useState<ActiveReference | null>(null)
  const [highlighted, setHighlighted] = useState(0)

  const options = useMemo(() => {
    if (!active) return []
    const source = active.kind === 'skill' ? menu.skills : menu.tools
    const query = active.query.toLowerCase()
    return source.filter((entry) => entry.name.toLowerCase().startsWith(query))
  }, [active, menu])

  const insert = (name: string) => {
    const element = area.current
    if (!element || !active) return
    const caret = element.selectionStart
    const marker = active.kind === 'skill' ? '@' : '/'
    // The trailing space is load-bearing: the backend only treats a marker as a
    // reference when it follows whitespace, so `@A@B` would silently be one ref.
    const next = `${content.slice(0, active.start)}${marker}${name} ${content.slice(caret)}`
    onChange(next)
    setActive(null)
    const position = active.start + name.length + 2
    requestAnimationFrame(() => {
      element.focus()
      element.setSelectionRange(position, position)
    })
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (!active || options.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlighted((current) => (current + 1) % options.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlighted((current) => (current - 1 + options.length) % options.length)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      insert(options[highlighted].name)
    } else if (event.key === 'Escape') {
      setActive(null)
    }
  }

  return (
    <div className="relative">
      <textarea
        ref={area}
        value={content}
        rows={16}
        placeholder="Instructions in markdown. Type @ for a skill, / for a tool."
        onChange={(event) => {
          onChange(event.target.value)
          setActive(activeReference(event.target.value, event.target.selectionStart))
          setHighlighted(0)
        }}
        onClick={() => {
          const element = area.current
          if (element) setActive(activeReference(element.value, element.selectionStart))
        }}
        onKeyDown={onKeyDown}
        onBlur={() => setActive(null)}
        className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-3 py-2 text-sm font-mono text-ink-800 dark:text-cream-100 resize-y"
      />

      {active && options.length > 0 && (
        <div className="absolute z-10 mt-1 w-[280px] rounded-lg border border-ink-100 dark:border-ink-600 bg-white dark:bg-ink-800 shadow-lg overflow-hidden">
          <div className="px-2 py-1 text-[9px] uppercase tracking-wider text-ink-400 bg-cream-100 dark:bg-ink-700/60">
            {active.kind === 'skill' ? 'Skills' : 'Tools'}
          </div>
          <ul className="max-h-52 overflow-y-auto">
            {options.map((entry, index) => (
              <li key={entry.name}>
                <button
                  type="button"
                  onMouseDown={(event) => {
                    event.preventDefault()
                    insert(entry.name)
                  }}
                  className={`flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left text-xs font-body ${
                    index === highlighted ? 'bg-cream-100 dark:bg-ink-700/60' : ''
                  }`}
                >
                  <span className="font-mono text-ink-800 dark:text-cream-100">
                    {active.kind === 'skill' ? '@' : '/'}
                    {entry.name}
                  </span>
                  <span className="max-w-[150px] truncate text-[10px] text-ink-400">
                    {entry.description}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {active && options.length === 0 && (
        <p className="mt-1 text-[11px] font-body text-ink-400">
          {active.kind === 'skill'
            ? 'No skill matches that name yet.'
            : 'No tool matches that name. Tool names come from the Tools section.'}
        </p>
      )}
    </div>
  )
}
