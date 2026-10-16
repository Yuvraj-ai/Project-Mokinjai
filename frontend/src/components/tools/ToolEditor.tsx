import { useEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import {
  createTool,
  parameterTypeLabel,
  updateTool,
  validateTool,
  type Tool,
  type ToolValidation,
} from '../../api/tools'
import { axiosDetail } from '../../api/client'
import SchemaPreview from '../structured-output/SchemaPreview'

const EXAMPLE = `def get_weather(city: str, units: str = "metric") -> str:
    """Report the current weather for a city.

    Args:
        city: The city to report on, e.g. Lisbon.
        units: Either "metric" or "imperial".
    """
    # The body runs in the sandbox. Return the text the model should see.
    return f"{city}: 18 degrees ({units})"
`

interface Props {
  workspaceId: string
  /** null starts a new tool. */
  tool: Tool | null
  onSaved: (tool: Tool) => void
  onClose: () => void
}

/** The code box, and beneath it what the code describes, recomputed as it is typed. */
export default function ToolEditor({ workspaceId, tool, onSaved, onClose }: Props) {
  const [code, setCode] = useState(tool?.code ?? EXAMPLE)
  const [validation, setValidation] = useState<ToolValidation | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Debounced, not queued. The counter is what stops a slow response for older text
  // from overwriting a fast one for newer text.
  const latest = useRef(0)

  useEffect(() => {
    if (!code.trim()) {
      setValidation(null)
      return
    }
    const request = ++latest.current
    const timer = setTimeout(() => {
      validateTool(workspaceId, code)
        .then((result) => {
          if (request === latest.current) setValidation(result)
        })
        .catch(() => {
          if (request === latest.current) setValidation(null)
        })
    }, 400)
    return () => clearTimeout(timer)
  }, [code, workspaceId])

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const saved = tool
        ? await updateTool(workspaceId, tool.id, code)
        : await createTool(workspaceId, code)
      onSaved(saved)
    } catch (caught: unknown) {
      setError(axiosDetail(caught) || 'Could not save this tool')
    } finally {
      setSaving(false)
    }
  }

  const schema = validation?.valid ? validation.schema : null

  return (
    <div className="mb-8 rounded-xl border border-ink-100/60 dark:border-ink-700/60 bg-white dark:bg-ink-800 p-5">
      <div className="flex items-end justify-between gap-4 mb-3">
        <div className="min-w-0">
          <div className="font-display text-2xl text-ink-900 dark:text-cream-100 truncate">
            {tool ? tool.name : 'New tool'}
          </div>
          <p className="text-xs font-body text-ink-400 mt-1">
            One Python function. Its docstring and type hints become the schema the model sees.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setCode(EXAMPLE)}
            className="rounded-lg border border-ink-100 dark:border-ink-600 px-3 py-1.5 text-xs font-body text-ink-500 dark:text-ink-200"
          >
            Reset example
          </button>
          <button
            onClick={onClose}
            className="rounded-lg border border-ink-100 dark:border-ink-600 px-3 py-1.5 text-xs font-body text-ink-500 dark:text-ink-200"
          >
            Close
          </button>
          <button
            onClick={() => void save()}
            disabled={saving || !validation?.valid}
            className="inline-flex items-center gap-2 rounded-lg bg-ink-800 dark:bg-cream-200 px-4 py-1.5 text-sm font-body font-medium text-cream-50 dark:text-ink-800 disabled:opacity-60"
          >
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />} Save
          </button>
        </div>
      </div>

      <textarea
        value={code}
        onChange={(event) => setCode(event.target.value)}
        rows={16}
        spellCheck={false}
        className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 p-3 text-[12px] leading-relaxed font-mono text-ink-800 dark:text-cream-100"
      />

      {error && (
        <p className="mt-3 text-sm font-body text-status-error whitespace-pre-wrap">{error}</p>
      )}

      <div className="mt-4 space-y-3">
        {validation === null && (
          <p className="text-xs font-body text-ink-400">Checking the code…</p>
        )}

        {validation && !validation.valid && (
          <div className="rounded-lg border border-status-error/40 bg-status-error/5 px-3 py-2.5">
            <p className="text-[11px] font-body font-medium text-status-error mb-1">
              This is not a tool yet
            </p>
            <ul className="space-y-1">
              {validation.errors.map((message) => (
                <li key={message} className="text-xs font-body text-status-error">
                  {message}
                </li>
              ))}
            </ul>
          </div>
        )}

        {schema && (
          <>
            <div className="rounded-lg border border-ink-100 dark:border-ink-700 px-3 py-2.5">
              <p className="text-[10px] uppercase tracking-wider font-semibold text-ink-400 mb-1">
                Description the model sees
              </p>
              <p className="text-sm font-body text-ink-700 dark:text-cream-200">
                {schema.description}
              </p>
            </div>

            <table className="w-full text-left">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-ink-400">
                  <th className="pb-1 font-semibold">Parameter</th>
                  <th className="pb-1 font-semibold">Type</th>
                  <th className="pb-1 font-semibold">Required</th>
                  <th className="pb-1 font-semibold">Description</th>
                </tr>
              </thead>
              <tbody>
                {schema.parameters.map((parameter) => (
                  <tr
                    key={parameter.name}
                    className="border-t border-ink-100/60 dark:border-ink-700/60"
                  >
                    <td className="py-1.5 font-mono text-xs text-ink-800 dark:text-cream-100">
                      {parameter.name}
                    </td>
                    <td className="py-1.5 font-mono text-xs text-ink-500 dark:text-ink-200">
                      {parameterTypeLabel(parameter)}
                    </td>
                    <td className="py-1.5 font-body text-xs text-ink-500 dark:text-ink-200">
                      {parameter.required ? 'yes' : 'no'}
                    </td>
                    <td className="py-1.5 font-body text-xs text-ink-500 dark:text-ink-200">
                      {parameter.description}
                    </td>
                  </tr>
                ))}
                {schema.parameters.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-2 text-xs font-body text-ink-400">
                      This tool takes no parameters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            <p className="text-xs font-body text-ink-400">
              Returns <span className="font-mono">{schema.returns}</span>
            </p>

            <SchemaPreview schema={schema.input_schema} />
          </>
        )}
      </div>
    </div>
  )
}
