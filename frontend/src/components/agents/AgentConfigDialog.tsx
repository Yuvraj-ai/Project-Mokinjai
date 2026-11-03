import { useEffect, useState } from 'react'
import { AlertTriangle, Trash2 } from 'lucide-react'
import {
  AGENT_DESCRIPTION_MAX,
  AGENT_NAME_MAX,
  AGENT_PROMPT_MAX,
  createAgent,
  deleteAgent,
  fieldErrors,
  updateAgent,
  type Agent,
  type AgentCapabilities,
  type AgentInput,
  type AgentOptions,
  type AgentParams,
  type WebSearchMethod,
} from '../../api/agents'
import { listPrompts, type PromptTemplate } from '../../api/prompts'
import { listDocuments, listFolders } from '../../api/files'
import {
  SEARCH_KEY_PROVIDERS,
  listSearchCredentials,
  saveSearchCredential,
  type SearchCredential,
} from '../../api/searchCredentials'
import LlmPicker from './LlmPicker'
import MultiSelect from './MultiSelect'
import NumberSlider from './NumberSlider'
import SkillPicker from './SkillPicker'
import FilePicker, { type FileSelection } from './FilePicker'
import DataSourcePicker, { type DataSourceSelection } from './DataSourcePicker'
import { listExternalDatabases, type ExternalDatabase } from '../../api/externalDatabases'
import Button from '../ui/Button'

const SOURCE_LABEL: Record<string, string> = {
  profile_override: 'set on the LLM profile',
  model_profile: 'from the model card',
  fallback: 'universal default',
}

const inputClass =
  'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring'
const selectClass =
  'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-ring'
const labelClass = 'mb-1.5 block text-[13px] font-medium text-ink'
const errorClass = 'mt-1 block text-xs text-status-error'

function blankInput(): AgentInput {
  return {
    name: '',
    description: null,
    llm_profile_id: '',
    system_prompt: '',
    source_prompt_id: null,
    params: { streaming: false },
    structured_output_id: null,
    web_search: null,
    skill_ids: [],
    tool_ids: [],
    folders: [],
    documents: [],
    connector_ids: [],
    subagent_ids: [],
    data_sources: [],
  }
}

function toInput(agent: Agent): AgentInput {
  return {
    name: agent.name,
    description: agent.description,
    llm_profile_id: agent.llm_profile_id ?? '',
    system_prompt: agent.system_prompt,
    source_prompt_id: agent.source_prompt_id,
    params: { ...agent.params },
    structured_output_id: agent.structured_output_id,
    web_search: agent.web_search,
    skill_ids: [...agent.skill_ids],
    tool_ids: [...agent.tool_ids],
    // Placeholder only: the resolved file set is hydrated asynchronously after mount.
    folders: [],
    documents: [],
    connector_ids: [...agent.connector_ids],
    subagent_ids: [...agent.subagent_ids],
    data_sources: agent.data_sources.map((item) => ({ id: item.id, tables: [...item.tables] })),
  }
}

function pruneParams(params: AgentParams, capabilities: AgentCapabilities | null): AgentParams {
  const pruned: AgentParams = { streaming: params.streaming ?? false }
  if (!capabilities) return pruned
  if (capabilities.temperature.supported && params.temperature !== undefined) {
    pruned.temperature = params.temperature
  }
  if (params.max_tokens !== undefined) {
    pruned.max_tokens = Math.min(capabilities.max_output_tokens, params.max_tokens)
  }
  if (capabilities.reasoning.supported && params.reasoning) pruned.reasoning = params.reasoning
  if (capabilities.advanced.top_p && params.top_p !== undefined) pruned.top_p = params.top_p
  if (capabilities.advanced.seed && params.seed !== undefined) pruned.seed = params.seed
  if (capabilities.advanced.stop && params.stop?.length) pruned.stop = params.stop
  return pruned
}

interface AgentConfigDialogProps {
  workspaceId: string
  options: AgentOptions
  agent: Agent | null
  initialName: string
  initialDescription: string
  onClose: () => void
  onSaved: (agent: Agent) => void
  onDeleted: (agentId: string) => void
}

export default function AgentConfigDialog({
  workspaceId,
  options,
  agent,
  initialName,
  initialDescription,
  onClose,
  onSaved,
  onDeleted,
}: AgentConfigDialogProps) {
  const [form, setForm] = useState<AgentInput>(() =>
    agent
      ? toInput(agent)
      : { ...blankInput(), name: initialName, description: initialDescription || null }
  )
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [connections, setConnections] = useState<ExternalDatabase[]>([])
  const [issues, setIssues] = useState<string[]>(agent?.issues ?? [])
  const [saving, setSaving] = useState(false)
  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [credentials, setCredentials] = useState<SearchCredential[]>([])
  const [keyDraft, setKeyDraft] = useState('')
  const [savingKey, setSavingKey] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [stopText, setStopText] = useState((agent?.params.stop ?? []).join(', '))
  const [filesLoading, setFilesLoading] = useState(agent !== null)
  const [fileCount, setFileCount] = useState(agent?.documents.length ?? 0)
  const [pickerOpen, setPickerOpen] = useState(false)

  useEffect(() => {
    listPrompts(workspaceId)
      .then((response) => setPrompts(response.prompts))
      .catch(() => {})
    listSearchCredentials(workspaceId)
      .then(setCredentials)
      .catch(() => {})
  }, [workspaceId])

  // `toInput` cannot invert the write-time rules from the resolved file set alone,
  // so the folder rules are rebuilt against the live file list once it is loaded.
  useEffect(() => {
    if (!agent) {
      setFilesLoading(false)
      return
    }
    let cancelled = false
    setFilesLoading(true)
    void Promise.all([listFolders(workspaceId), listDocuments(workspaceId)])
      .then(([folders, docList]) => {
        if (cancelled) return
        const attached = new Set(agent.documents.map((doc) => doc.id))
        const filesByFolder = new Map<string, string[]>()
        for (const doc of docList.documents) {
          if (!doc.folder_id) continue
          const ids = filesByFolder.get(doc.folder_id) ?? []
          ids.push(doc.id)
          filesByFolder.set(doc.folder_id, ids)
        }
        const selection: FileSelection = { folders: [], documents: [] }
        for (const [folderId, fileIds] of filesByFolder) {
          if (!fileIds.some((id) => attached.has(id))) continue
          selection.folders.push({
            id: folderId,
            exclude_document_ids: fileIds.filter((id) => !attached.has(id)),
          })
        }
        // A file whose source folder lost its live files (e.g. the folder was
        // emptied or renamed away) cannot be expressed as a rule, so it stays a
        // loose id and is never silently dropped.
        const ruleFolders = new Set(selection.folders.map((rule) => rule.id))
        selection.documents = agent.documents
          .filter(
            (doc) => doc.source_folder_id === null || !ruleFolders.has(doc.source_folder_id)
          )
          .map((doc) => doc.id)
        setForm((previous) => ({ ...previous, ...selection }))
        setFileCount(attached.size)
        setFilesLoading(false)
      })
      .catch((caught) => {
        if (cancelled) return
        setForm((previous) => ({
          ...previous,
          folders: [],
          documents: agent.documents.map((doc) => doc.id),
        }))
        setFilesLoading(false)
        setMessage(fieldErrors(caught).message ?? 'Could not load the workspace files.')
      })
    return () => {
      cancelled = true
    }
  }, [agent, workspaceId])

  useEffect(() => {
    listExternalDatabases(workspaceId)
      .then(setConnections)
      .catch(() => setConnections([]))
  }, [workspaceId])

  const selectedOption = options.llm_profiles.find((item) => item.id === form.llm_profile_id)
  const capabilities =
    selectedOption?.capabilities ??
    (agent && agent.llm_profile_id === form.llm_profile_id ? agent.capabilities : null)

  const setField = <K extends keyof AgentInput>(key: K, value: AgentInput[K]) =>
    setForm((previous) => ({ ...previous, [key]: value }))

  const setParams = (patch: Partial<AgentParams>) =>
    setForm((previous) => ({ ...previous, params: { ...previous.params, ...patch } }))

  const chooseLlm = (option: AgentOptions['llm_profiles'][number] | null) => {
    const caps = option?.capabilities ?? null
    const params: AgentParams = { streaming: false }
    if (caps?.temperature.supported) {
      params.temperature = Math.min(caps.temperature.maximum, Math.max(caps.temperature.minimum, 0.7))
    }
    if (caps) params.max_tokens = caps.max_output_tokens
    if (caps?.reasoning.supported && caps.reasoning.default) params.reasoning = caps.reasoning.default
    setForm((previous) => ({
      ...previous,
      llm_profile_id: option?.id ?? '',
      params,
      web_search:
        previous.web_search?.method === 'native' && !caps?.native_web_search
          ? null
          : previous.web_search,
    }))
    setErrors({})
  }

  const hasKey = (provider: WebSearchMethod) =>
    credentials.some((credential) => credential.provider === provider && credential.has_key)

  const saveKey = async (provider: WebSearchMethod) => {
    if (!keyDraft.trim()) return
    setSavingKey(true)
    try {
      await saveSearchCredential(workspaceId, provider, keyDraft.trim())
      setCredentials(await listSearchCredentials(workspaceId))
      setKeyDraft('')
      setErrors((previous) => ({ ...previous, web_search: '' }))
    } catch (caught) {
      setMessage(fieldErrors(caught).message ?? 'Could not save that key.')
    } finally {
      setSavingKey(false)
    }
  }

  const save = async () => {
    const nextErrors: Record<string, string> = {}
    if (!form.name.trim()) nextErrors.name = 'A name is required.'
    if (!form.llm_profile_id) nextErrors.llm_profile_id = 'Choose a model.'
    if (!form.system_prompt.trim()) nextErrors.system_prompt = 'A system prompt is required.'
    if (
      form.web_search?.enabled &&
      form.web_search.method !== 'native' &&
      !hasKey(form.web_search.method)
    ) {
      nextErrors.web_search = `Add an ${form.web_search.method} API key first.`
    }
    setErrors(nextErrors)
    setMessage(null)
    if (Object.keys(nextErrors).length > 0) return

    const payload: AgentInput = {
      ...form,
      name: form.name.trim(),
      description: form.description?.trim() || null,
      params: pruneParams(form.params, capabilities),
      web_search: form.web_search?.enabled ? form.web_search : null,
    }

    setSaving(true)
    try {
      const saved = agent
        ? await updateAgent(workspaceId, agent.id, payload)
        : await createAgent(workspaceId, payload)
      setIssues(saved.issues)
      setForm(toInput(saved))
      onSaved(saved)
    } catch (caught) {
      const parsed = fieldErrors(caught)
      setErrors(parsed.fields)
      setMessage(parsed.message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!agent) return
    if (!window.confirm(`Delete “${agent.name}”? This cannot be undone.`)) return
    try {
      await deleteAgent(workspaceId, agent.id)
      onDeleted(agent.id)
    } catch (caught) {
      setMessage(fieldErrors(caught).message ?? 'Could not delete this agent.')
    }
  }

  const fieldError = (field: string) => errors[field] || undefined

  return (
    <div className="fixed inset-0 z-40 flex bg-black/40 p-2 sm:p-4 dark:bg-black/60">
      <div className="flex w-full flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-drawer animate-scale-in max-h-full">
        <header className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-ink">
              {agent ? agent.name : form.name || 'New agent'}
            </h2>
            <p className="mt-0.5 font-mono text-xs text-ink-subtle">
              {agent ? `Created ${new Date(agent.created_at).toLocaleString()}` : 'Unsaved'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {agent && (
              <button
                type="button"
                onClick={remove}
                title="Delete agent"
                aria-label="Delete agent"
                className="rounded-md p-2 text-ink-subtle transition-colors hover:bg-status-error-soft hover:text-status-error"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
            <Button variant="ghost" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </header>

        <div className="flex flex-1 flex-col gap-6 overflow-y-auto p-5 lg:flex-row">
          <section className="w-full space-y-4 lg:w-[340px] lg:shrink-0">
            <h3 className="text-[13px] font-semibold text-ink">Parameters</h3>

            <label className="block">
              <span className={labelClass}>Agent name</span>
              <input
                value={form.name}
                maxLength={AGENT_NAME_MAX}
                onChange={(event) => setField('name', event.target.value)}
                className={inputClass}
              />
              {fieldError('name') && <span className={errorClass}>{fieldError('name')}</span>}
            </label>

            <label className="block">
              <span className={labelClass}>Description</span>
              <input
                value={form.description ?? ''}
                maxLength={AGENT_DESCRIPTION_MAX}
                onChange={(event) => setField('description', event.target.value)}
                className={inputClass}
              />
            </label>

            <div>
              <LlmPicker options={options.llm_profiles} value={form.llm_profile_id} onChange={chooseLlm} />
              {fieldError('llm_profile_id') && (
                <span className={errorClass}>{fieldError('llm_profile_id')}</span>
              )}
            </div>

            {capabilities?.temperature.supported && (
              <NumberSlider
                label="Temperature"
                value={form.params.temperature ?? capabilities.temperature.minimum}
                min={capabilities.temperature.minimum}
                max={capabilities.temperature.maximum}
                step={0.05}
                onChange={(value) => setParams({ temperature: value })}
              />
            )}

            <NumberSlider
              label="Max completions"
              value={form.params.max_tokens ?? capabilities?.max_output_tokens ?? 4096}
              min={1}
              max={capabilities?.max_output_tokens ?? 4096}
              disabled={!capabilities}
              hint={
                capabilities
                  ? `Ceiling ${capabilities.max_output_tokens} — ${SOURCE_LABEL[capabilities.max_output_source] ?? capabilities.max_output_source}`
                  : 'Select a model to resolve the ceiling.'
              }
              onChange={(value) => setParams({ max_tokens: value })}
            />
            {fieldError('params.max_tokens') && (
              <span className={errorClass}>{fieldError('params.max_tokens')}</span>
            )}

            {capabilities?.reasoning.supported && (
              <label className="block">
                <span className={labelClass}>Reasoning effort</span>
                <select
                  value={form.params.reasoning ?? ''}
                  onChange={(event) => setParams({ reasoning: event.target.value || undefined })}
                  className={selectClass}
                >
                  <option value="">Model default</option>
                  {capabilities.reasoning.levels.map((level) => (
                    <option key={level} value={level}>
                      {level}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <label className="flex items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                checked={form.params.streaming ?? false}
                onChange={(event) => setParams({ streaming: event.target.checked })}
                className="accent-primary"
              />
              Stream tokens
            </label>

            <div>
              <button
                type="button"
                onClick={() => setShowAdvanced((current) => !current)}
                className="text-[13px] font-medium text-ink-muted transition-colors hover:text-ink"
              >
                {showAdvanced ? '−' : '+'} Advanced
              </button>
              {showAdvanced && capabilities && (
                <div className="mt-3 space-y-4 rounded-lg border border-line p-3.5">
                  {capabilities.advanced.top_p && (
                    <NumberSlider
                      label="Top P"
                      value={form.params.top_p ?? 1}
                      min={0}
                      max={1}
                      step={0.05}
                      onChange={(value) => setParams({ top_p: value })}
                    />
                  )}
                  {capabilities.advanced.seed && (
                    <label className="block">
                      <span className={labelClass}>Seed</span>
                      <input
                        type="number"
                        value={form.params.seed ?? ''}
                        onChange={(event) =>
                          setParams({
                            seed: event.target.value === '' ? undefined : Number(event.target.value),
                          })
                        }
                        className={inputClass}
                      />
                    </label>
                  )}
                  {capabilities.advanced.stop && (
                    <label className="block">
                      <span className={labelClass}>Stop sequences (comma separated)</span>
                      <input
                        value={stopText}
                        onChange={(event) => {
                          setStopText(event.target.value)
                          setParams({
                            stop: event.target.value
                              .split(',')
                              .map((entry) => entry.trim())
                              .filter(Boolean),
                          })
                        }}
                        className={inputClass}
                      />
                    </label>
                  )}
                </div>
              )}
            </div>
          </section>

          <section className="flex-1 space-y-6">
            <h3 className="text-[13px] font-semibold text-ink">Configuration</h3>

            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className={labelClass + ' mb-0'}>System prompt</span>
                <select
                  value=""
                  onChange={(event) => {
                    const prompt = prompts.find((item) => item.id === event.target.value)
                    if (prompt) {
                      setForm((previous) => ({
                        ...previous,
                        system_prompt: prompt.content,
                        source_prompt_id: prompt.id,
                      }))
                    }
                  }}
                  className="rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink-muted focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">Insert from Prompts…</option>
                  {prompts.map((prompt) => (
                    <option key={prompt.id} value={prompt.id}>
                      {prompt.name}
                    </option>
                  ))}
                </select>
              </div>
              <textarea
                value={form.system_prompt}
                rows={6}
                maxLength={AGENT_PROMPT_MAX}
                onChange={(event) => setField('system_prompt', event.target.value)}
                className="w-full resize-y rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-ring"
              />
              {form.source_prompt_id && (
                <span className="mt-1 block text-xs text-ink-subtle">
                  Copied from a prompt; later edits there do not change this agent.
                </span>
              )}
              {fieldError('system_prompt') && (
                <span className={errorClass}>{fieldError('system_prompt')}</span>
              )}
            </div>

            <div className="rounded-lg border border-line p-3.5">
              <label className="mb-2 flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  checked={form.structured_output_id !== null}
                  onChange={(event) =>
                    setField(
                      'structured_output_id',
                      event.target.checked ? (options.structured_outputs[0]?.id ?? '') : null
                    )
                  }
                  className="accent-primary"
                />
                Structured output
              </label>
              {form.structured_output_id !== null && (
                <select
                  value={form.structured_output_id}
                  onChange={(event) => setField('structured_output_id', event.target.value)}
                  className={selectClass}
                >
                  {options.structured_outputs.map((output) => (
                    <option key={output.id} value={output.id}>
                      {output.name}
                    </option>
                  ))}
                </select>
              )}
              {fieldError('structured_output_id') && (
                <span className={errorClass}>{fieldError('structured_output_id')}</span>
              )}
            </div>

            <div className="rounded-lg border border-line p-3.5">
              <label className="mb-2 flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  checked={form.web_search?.enabled ?? false}
                  onChange={(event) =>
                    setField(
                      'web_search',
                      event.target.checked
                        ? { enabled: true, method: capabilities?.native_web_search ? 'native' : 'tavily' }
                        : null
                    )
                  }
                  className="accent-primary"
                />
                Web search
              </label>
              {form.web_search?.enabled && (
                <div className="space-y-2">
                  <select
                    value={form.web_search.method}
                    onChange={(event) =>
                      setField('web_search', {
                        enabled: true,
                        method: event.target.value as WebSearchMethod,
                      })
                    }
                    className={selectClass}
                  >
                    {SEARCH_KEY_PROVIDERS.map((provider) => (
                      <option key={provider} value={provider}>
                        {provider}
                      </option>
                    ))}
                    {capabilities?.native_web_search && (
                      <option value="native">Provider's own search ({capabilities.provider})</option>
                    )}
                  </select>

                  {form.web_search.method !== 'native' &&
                    (hasKey(form.web_search.method) ? (
                      <p className="text-xs text-status-success">
                        A {form.web_search.method} API key is stored.
                      </p>
                    ) : (
                      <div className="flex items-center gap-2">
                        <input
                          type="password"
                          value={keyDraft}
                          onChange={(event) => setKeyDraft(event.target.value)}
                          placeholder={`${form.web_search.method} API key`}
                          className="flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                        <Button
                          size="sm"
                          disabled={savingKey || !keyDraft.trim()}
                          onClick={() => void saveKey(form.web_search?.method as WebSearchMethod)}
                        >
                          {savingKey ? 'Saving…' : 'Save key'}
                        </Button>
                      </div>
                    ))}
                </div>
              )}
              {fieldError('web_search') && (
                <span className={errorClass}>{fieldError('web_search')}</span>
              )}
            </div>

            <SkillPicker
              skills={options.skills}
              tools={options.tools}
              skillIds={form.skill_ids}
              toolIds={form.tool_ids}
              onSkillsChange={(ids) => setField('skill_ids', ids)}
              onToolsChange={(ids) => setField('tool_ids', ids)}
              skillError={fieldError('skill_ids')}
              toolError={fieldError('tool_ids')}
            />

            <div className="rounded-lg border border-line p-3.5">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-[13px] font-medium text-ink">Files</span>
                <span className="font-mono text-xs text-ink-subtle">
                  {filesLoading
                    ? 'Checking files…'
                    : fileCount > 0
                      ? `${fileCount} file(s) attached`
                      : 'No files attached'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={filesLoading}
                  onClick={() => setPickerOpen(true)}
                >
                  Edit files
                </Button>
                {fieldError('documents') && (
                  <span className="text-xs text-status-error">{fieldError('documents')}</span>
                )}
              </div>
              <FilePicker
                workspaceId={workspaceId}
                value={{ folders: form.folders, documents: form.documents }}
                onChange={(value) => setForm((previous) => ({ ...previous, ...value }))}
                onSummary={setFileCount}
                open={pickerOpen}
                onClose={() => setPickerOpen(false)}
              />
            </div>

            <DataSourcePicker
              connections={connections}
              value={form.data_sources as DataSourceSelection}
              onChange={(value) => setForm((previous) => ({ ...previous, data_sources: value }))}
              error={fieldError('data_sources')}
            />

            <MultiSelect
              label="Connectors"
              options={options.connectors}
              values={form.connector_ids}
              onChange={(ids) => setField('connector_ids', ids)}
              hint={(option) => option.status ?? undefined}
              disabled={(option) => option.status !== 'enabled'}
              emptyText="No connectors yet."
              error={fieldError('connector_ids')}
            />

            <MultiSelect
              label="Subagents"
              options={options.agents}
              values={form.subagent_ids}
              onChange={(ids) => setField('subagent_ids', ids)}
              emptyText="No other agents yet."
              error={fieldError('subagent_ids')}
            />

            {issues.length > 0 && (
              <div className="rounded-lg border border-status-warning/30 bg-status-warning-soft p-3.5">
                <p className="mb-1.5 flex items-center gap-2 text-[13px] font-semibold text-status-warning">
                  <AlertTriangle className="h-3.5 w-3.5" aria-hidden /> This agent needs attention
                </p>
                <ul className="list-inside list-disc text-[13px] text-ink">
                  {issues.map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}

            {message && (
              <p className="rounded-lg bg-status-error-soft px-3 py-2 text-[13px] text-status-error">
                {message}
              </p>
            )}
          </section>
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-line px-5 py-3.5">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" disabled={saving || filesLoading} onClick={() => void save()}>
            {saving ? 'Saving…' : agent ? 'Save changes' : 'Create agent'}
          </Button>
        </footer>
      </div>
    </div>
  )
}
