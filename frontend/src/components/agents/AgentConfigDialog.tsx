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

const SOURCE_LABEL: Record<string, string> = {
  profile_override: 'set on the LLM profile',
  model_profile: 'from the model card',
  fallback: 'universal default',
}

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
    <div className="fixed inset-0 z-40 flex bg-ink-900/30 p-2 sm:p-4">
      <div className="flex w-full flex-col overflow-hidden rounded-xl border border-ink-100/60 dark:border-ink-700/60 bg-white dark:bg-ink-800 shadow-xl">
        <header className="flex items-center justify-between border-b border-ink-100/60 dark:border-ink-700/60 px-5 py-3">
          <div className="min-w-0">
            <h2 className="truncate font-display text-xl text-ink-800 dark:text-cream-100">
              {agent ? agent.name : form.name || 'New agent'}
            </h2>
            <p className="text-[10px] text-ink-400">
              {agent ? `Created ${new Date(agent.created_at).toLocaleString()}` : 'Unsaved'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {agent && (
              <button
                type="button"
                onClick={remove}
                title="Delete agent"
                className="rounded-lg p-2 text-ink-300 hover:text-status-error"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-3 py-1.5 text-xs text-ink-500 hover:bg-ink-50 dark:hover:bg-ink-700"
            >
              Close
            </button>
          </div>
        </header>

        <div className="flex flex-1 flex-col gap-5 overflow-y-auto p-5 lg:flex-row">
          <section className="w-full space-y-4 lg:w-[340px] lg:shrink-0">
            <h3 className="text-[10px] uppercase tracking-wider font-semibold text-ink-400">
              Parameters
            </h3>

            <label className="block">
              <span className="mb-1 block text-[10px] uppercase tracking-wider font-semibold text-ink-400">
                Agent name
              </span>
              <input
                value={form.name}
                maxLength={AGENT_NAME_MAX}
                onChange={(event) => setField('name', event.target.value)}
                className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-sm text-ink-800 dark:text-cream-100"
              />
              {fieldError('name') && (
                <span className="mt-1 block text-[11px] text-status-error">{fieldError('name')}</span>
              )}
            </label>

            <label className="block">
              <span className="mb-1 block text-[10px] uppercase tracking-wider font-semibold text-ink-400">
                Description
              </span>
              <input
                value={form.description ?? ''}
                maxLength={AGENT_DESCRIPTION_MAX}
                onChange={(event) => setField('description', event.target.value)}
                className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-sm text-ink-800 dark:text-cream-100"
              />
            </label>

            <div>
              <LlmPicker options={options.llm_profiles} value={form.llm_profile_id} onChange={chooseLlm} />
              {fieldError('llm_profile_id') && (
                <span className="mt-1 block text-[11px] text-status-error">
                  {fieldError('llm_profile_id')}
                </span>
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
              <span className="block text-[11px] text-status-error">{fieldError('params.max_tokens')}</span>
            )}

            {capabilities?.reasoning.supported && (
              <label className="block">
                <span className="mb-1 block text-[10px] uppercase tracking-wider font-semibold text-ink-400">
                  Reasoning effort
                </span>
                <select
                  value={form.params.reasoning ?? ''}
                  onChange={(event) => setParams({ reasoning: event.target.value || undefined })}
                  className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-xs text-ink-800 dark:text-cream-100"
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

            <label className="flex items-center gap-2 text-xs text-ink-600 dark:text-ink-200">
              <input
                type="checkbox"
                checked={form.params.streaming ?? false}
                onChange={(event) => setParams({ streaming: event.target.checked })}
                className="accent-[#C4956A]"
              />
              Stream tokens
            </label>

            <div>
              <button
                type="button"
                onClick={() => setShowAdvanced((current) => !current)}
                className="text-[10px] uppercase tracking-wider font-semibold text-ink-400 hover:text-ink-600"
              >
                {showAdvanced ? '−' : '+'} Advanced
              </button>
              {showAdvanced && capabilities && (
                <div className="mt-3 space-y-4 rounded-lg border border-ink-100/70 dark:border-ink-700/70 p-3">
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
                      <span className="mb-1 block text-[10px] uppercase tracking-wider font-semibold text-ink-400">
                        Seed
                      </span>
                      <input
                        type="number"
                        value={form.params.seed ?? ''}
                        onChange={(event) =>
                          setParams({
                            seed: event.target.value === '' ? undefined : Number(event.target.value),
                          })
                        }
                        className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-xs text-ink-800 dark:text-cream-100"
                      />
                    </label>
                  )}
                  {capabilities.advanced.stop && (
                    <label className="block">
                      <span className="mb-1 block text-[10px] uppercase tracking-wider font-semibold text-ink-400">
                        Stop sequences (comma separated)
                      </span>
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
                        className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-xs text-ink-800 dark:text-cream-100"
                      />
                    </label>
                  )}
                </div>
              )}
            </div>
          </section>

          <section className="flex-1 space-y-5">
            <h3 className="text-[10px] uppercase tracking-wider font-semibold text-ink-400">
              Configuration
            </h3>

            <div>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-400">
                  System prompt
                </span>
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
                  className="rounded-md border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-1.5 py-0.5 text-[10px] text-ink-500 dark:text-ink-200"
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
                className="w-full resize-y rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-2 text-xs text-ink-800 dark:text-cream-100"
              />
              {form.source_prompt_id && (
                <span className="mt-1 block text-[10px] text-ink-400">
                  Copied from a prompt; later edits there do not change this agent.
                </span>
              )}
              {fieldError('system_prompt') && (
                <span className="mt-1 block text-[11px] text-status-error">
                  {fieldError('system_prompt')}
                </span>
              )}
            </div>

            <div className="rounded-lg border border-ink-100/70 dark:border-ink-700/70 p-3">
              <label className="mb-2 flex items-center gap-2 text-xs text-ink-600 dark:text-ink-200">
                <input
                  type="checkbox"
                  checked={form.structured_output_id !== null}
                  onChange={(event) =>
                    setField(
                      'structured_output_id',
                      event.target.checked ? (options.structured_outputs[0]?.id ?? '') : null
                    )
                  }
                  className="accent-[#C4956A]"
                />
                Structured output
              </label>
              {form.structured_output_id !== null && (
                <select
                  value={form.structured_output_id}
                  onChange={(event) => setField('structured_output_id', event.target.value)}
                  className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-xs text-ink-800 dark:text-cream-100"
                >
                  {options.structured_outputs.map((output) => (
                    <option key={output.id} value={output.id}>
                      {output.name}
                    </option>
                  ))}
                </select>
              )}
              {fieldError('structured_output_id') && (
                <span className="mt-1 block text-[11px] text-status-error">
                  {fieldError('structured_output_id')}
                </span>
              )}
            </div>

            <div className="rounded-lg border border-ink-100/70 dark:border-ink-700/70 p-3">
              <label className="mb-2 flex items-center gap-2 text-xs text-ink-600 dark:text-ink-200">
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
                  className="accent-[#C4956A]"
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
                    className="w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-xs text-ink-800 dark:text-cream-100"
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
                      <p className="text-[10px] text-status-success">
                        A {form.web_search.method} API key is stored.
                      </p>
                    ) : (
                      <div className="flex items-center gap-2">
                        <input
                          type="password"
                          value={keyDraft}
                          onChange={(event) => setKeyDraft(event.target.value)}
                          placeholder={`${form.web_search.method} API key`}
                          className="flex-1 rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-xs text-ink-800 dark:text-cream-100"
                        />
                        <button
                          type="button"
                          disabled={savingKey || !keyDraft.trim()}
                          onClick={() => void saveKey(form.web_search?.method as WebSearchMethod)}
                          className="rounded-lg bg-accent-warm px-3 py-1.5 text-xs text-white disabled:opacity-50"
                        >
                          {savingKey ? 'Saving…' : 'Save key'}
                        </button>
                      </div>
                    ))}
                </div>
              )}
              {fieldError('web_search') && (
                <span className="mt-1 block text-[11px] text-status-error">
                  {fieldError('web_search')}
                </span>
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

            <div className="rounded-lg border border-ink-100/70 dark:border-ink-700/70 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-400">
                  Files
                </span>
                <span className="text-[11px] text-ink-500 dark:text-ink-300">
                  {filesLoading
                    ? 'Checking files…'
                    : fileCount > 0
                      ? `${fileCount} file(s) attached`
                      : 'No files attached'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  disabled={filesLoading}
                  onClick={() => setPickerOpen(true)}
                  className="rounded-lg border border-ink-100 dark:border-ink-600 px-3 py-1.5 text-xs text-ink-600 dark:text-ink-200 hover:bg-ink-50 dark:hover:bg-ink-700 disabled:opacity-50"
                >
                  Edit files
                </button>
                {fieldError('documents') && (
                  <span className="text-[11px] text-status-error">{fieldError('documents')}</span>
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
              <div className="rounded-lg border border-status-warning/40 bg-status-warning/5 p-3">
                <p className="mb-1 flex items-center gap-2 text-[11px] font-semibold text-status-warning">
                  <AlertTriangle className="h-3 w-3" /> This agent needs attention
                </p>
                <ul className="list-inside list-disc text-[11px] text-ink-600 dark:text-ink-200">
                  {issues.map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}

            {message && (
              <p className="rounded-lg border border-status-error/40 px-3 py-2 text-[11px] text-status-error">
                {message}
              </p>
            )}
          </section>
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-ink-100/60 dark:border-ink-700/60 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-xs text-ink-500 hover:bg-ink-50 dark:hover:bg-ink-700"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={saving || filesLoading}
            onClick={() => void save()}
            className="rounded-lg bg-accent-warm px-4 py-1.5 text-xs text-white disabled:opacity-50"
          >
            {saving ? 'Saving…' : agent ? 'Save changes' : 'Create agent'}
          </button>
        </footer>
      </div>
    </div>
  )
}
