import { useEffect, useState } from 'react'
import { Bot, Loader2, Plus, Trash2 } from 'lucide-react'
import { listWorkspaces } from '../api/workspaces'
import {
  deleteLlmProfile,
  listLlmProfiles,
  lookupContextWindow,
  testLlmProfile,
  type LlmProfile,
  type LlmProvider,
} from '../api/llmProfiles'

function axiosDetail(error: unknown): string | null {
  if (!error || typeof error !== 'object' || !('response' in error)) return null
  const response = error.response
  if (!response || typeof response !== 'object' || !('data' in response)) return null
  const data = response.data
  if (!data || typeof data !== 'object' || !('detail' in data)) return null
  return typeof data.detail === 'string' ? data.detail : null
}

const PROVIDERS: { value: LlmProvider; label: string }[] = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'custom', label: 'Custom' },
]

const emptyForm = {
  name: '',
  provider: 'openai' as LlmProvider,
  model_id: '',
  api_key: '',
  base_url: '',
  context_window: '',
  compaction_at_tokens: '',
  input_price_per_million: '',
  output_price_per_million: '',
  cache_price_per_million: '',
  profile_id: null as string | null,
}

export default function LlmProfilesPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [profiles, setProfiles] = useState<LlmProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [knownWindow, setKnownWindow] = useState<number | null>(null)
  const [testing, setTesting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    listWorkspaces()
      .then(async (workspaces) => {
        if (!workspaces?.length) return
        const id = workspaces[0].id
        setWorkspaceId(id)
        setProfiles(await listLlmProfiles(id))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const setField = (key: keyof typeof emptyForm, value: string) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const refreshWindow = async (provider: LlmProvider, modelId: string) => {
    if (!workspaceId || provider === 'custom' || !modelId.trim()) {
      setKnownWindow(null)
      return
    }
    try {
      const lookup = await lookupContextWindow(workspaceId, provider, modelId.trim())
      setKnownWindow(lookup.known ? lookup.max_input_tokens : null)
      if (lookup.known && lookup.max_input_tokens) {
        setForm((current) => ({
          ...current,
          compaction_at_tokens: current.compaction_at_tokens || String(Math.floor(lookup.max_input_tokens! * 0.8)),
        }))
      }
    } catch {
      setKnownWindow(null)
    }
  }

  const openNew = () => {
    setForm(emptyForm)
    setKnownWindow(null)
    setFormError(null)
    setShowForm(true)
  }

  const openExisting = (profile: LlmProfile) => {
    setForm({
      name: profile.name,
      provider: profile.provider,
      model_id: profile.model_id,
      api_key: '',
      base_url: profile.base_url || '',
      context_window: String(profile.context_window),
      compaction_at_tokens: String(profile.compaction_at_tokens),
      input_price_per_million: String(profile.input_price_per_million),
      output_price_per_million: String(profile.output_price_per_million),
      cache_price_per_million: String(profile.cache_price_per_million),
      profile_id: profile.id,
    })
    setKnownWindow(null)
    setFormError(profile.last_error)
    setShowForm(true)
    void refreshWindow(profile.provider, profile.model_id)
  }

  const handleTest = async () => {
    if (!workspaceId) return
    setTesting(true)
    setFormError(null)
    try {
      const saved = await testLlmProfile(workspaceId, {
        name: form.name.trim(),
        provider: form.provider,
        model_id: form.model_id.trim(),
        api_key: form.api_key,
        base_url: form.provider === 'custom' ? form.base_url.trim() : null,
        context_window: knownWindow ? null : Number(form.context_window),
        compaction_at_tokens: form.compaction_at_tokens ? Number(form.compaction_at_tokens) : null,
        input_price_per_million: Number(form.input_price_per_million),
        output_price_per_million: Number(form.output_price_per_million),
        cache_price_per_million: Number(form.cache_price_per_million),
        profile_id: form.profile_id,
      })
      setProfiles((current) => {
        const index = current.findIndex((profile) => profile.id === saved.id)
        if (index >= 0) {
          const next = [...current]
          next[index] = saved
          return next
        }
        return [saved, ...current]
      })
      setForm((current) => ({ ...current, profile_id: saved.id, api_key: '' }))
      setFormError(saved.status === 'failed' ? saved.last_error : null)
    } catch (error: unknown) {
      const detail = axiosDetail(error)
      setFormError(detail || 'Test failed before a profile could be saved')
    } finally {
      setTesting(false)
    }
  }

  const handleDelete = async (profileId: string) => {
    if (!workspaceId) return
    await deleteLlmProfile(workspaceId, profileId)
    setProfiles((current) => current.filter((profile) => profile.id !== profileId))
    if (form.profile_id === profileId) setShowForm(false)
  }

  if (loading || !workspaceId) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-5 h-5 text-accent animate-spin" />
      </div>
    )
  }

  const windowLabel = knownWindow
    ? `Context window ${knownWindow.toLocaleString()} from the model profile`
    : 'Context window is required for this model id'

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="flex items-end justify-between mb-8">
        <div>
          <h1 className="text-3xl font-display text-ink-900 dark:text-cream-100 tracking-tight leading-none">
            LLMs
          </h1>
          <p className="text-ink-400 dark:text-ink-300 mt-2 text-sm font-body">
            A model can be used in agent creation only after a passing connection test.
          </p>
        </div>
        <button
          onClick={openNew}
          className="inline-flex items-center gap-2 bg-ink-800 dark:bg-cream-200 hover:bg-ink-900 dark:hover:bg-cream-300 text-cream-50 dark:text-ink-800 font-body font-medium py-2 px-5 rounded-lg text-sm"
        >
          <Plus className="w-4 h-4" /> Add LLM
        </button>
      </div>

      {showForm && (
        <form
          className="mb-8 rounded-xl border border-ink-100/60 dark:border-ink-700/60 bg-white dark:bg-ink-800 p-5 space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            void handleTest()
          }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block text-xs font-body text-ink-400">
              Title
              <input value={form.name} onChange={(event) => setField('name', event.target.value)} required
                className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100" />
            </label>
            <label className="block text-xs font-body text-ink-400">
              Provider
              <select value={form.provider} onChange={(event) => {
                const provider = event.target.value as LlmProvider
                setField('provider', provider)
                setKnownWindow(null)
                void refreshWindow(provider, form.model_id)
              }} className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100">
                {PROVIDERS.map((provider) => (
                  <option key={provider.value} value={provider.value}>{provider.label}</option>
                ))}
              </select>
            </label>
            <label className="block text-xs font-body text-ink-400">
              Model id
              <input value={form.model_id} onChange={(event) => setField('model_id', event.target.value)}
                onBlur={() => void refreshWindow(form.provider, form.model_id)} required
                className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100" />
            </label>
            <label className="block text-xs font-body text-ink-400">
              API key {form.profile_id ? '(blank keeps the saved key)' : ''}
              <input type="password" value={form.api_key} onChange={(event) => setField('api_key', event.target.value)}
                required={!form.profile_id} autoComplete="off"
                className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100" />
            </label>
            {form.provider === 'custom' && (
              <label className="block text-xs font-body text-ink-400 sm:col-span-2">
                Base URL
                <input value={form.base_url} onChange={(event) => setField('base_url', event.target.value)} required
                  placeholder="https://example.com/v1"
                  className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100" />
              </label>
            )}
            {knownWindow ? (
              <p className="text-xs font-body text-ink-500 sm:col-span-2">{windowLabel}</p>
            ) : (
              <label className="block text-xs font-body text-ink-400">
                Context window
                <input type="number" min={1} value={form.context_window}
                  onChange={(event) => {
                    setField('context_window', event.target.value)
                    if (!form.compaction_at_tokens && event.target.value) {
                      setField('compaction_at_tokens', String(Math.floor(Number(event.target.value) * 0.8)))
                    }
                  }} required
                  className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100" />
              </label>
            )}
            <label className="block text-xs font-body text-ink-400">
              Compact after tokens
              <input type="number" min={1} value={form.compaction_at_tokens}
                onChange={(event) => setField('compaction_at_tokens', event.target.value)} required
                className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100" />
            </label>
            <label className="block text-xs font-body text-ink-400">
              Input $ / 1M tokens
              <input type="number" min={0} step="0.0001" value={form.input_price_per_million}
                onChange={(event) => setField('input_price_per_million', event.target.value)} required
                className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100" />
            </label>
            <label className="block text-xs font-body text-ink-400">
              Output $ / 1M tokens
              <input type="number" min={0} step="0.0001" value={form.output_price_per_million}
                onChange={(event) => setField('output_price_per_million', event.target.value)} required
                className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100" />
            </label>
            <label className="block text-xs font-body text-ink-400">
              Cache $ / 1M tokens
              <input type="number" min={0} step="0.0001" value={form.cache_price_per_million}
                onChange={(event) => setField('cache_price_per_million', event.target.value)} required
                className="mt-1 w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-ink-50/30 dark:bg-ink-700/50 px-3 py-2 text-sm text-ink-800 dark:text-cream-100" />
            </label>
          </div>
          {formError && (
            <p className="text-sm font-body text-status-error whitespace-pre-wrap">{formError}</p>
          )}
          <button type="submit" disabled={testing}
            className="inline-flex items-center gap-2 bg-ink-800 dark:bg-cream-200 text-cream-50 dark:text-ink-800 font-body font-medium py-2 px-5 rounded-lg text-sm disabled:opacity-60">
            {testing && <Loader2 className="w-4 h-4 animate-spin" />}
            Test connection
          </button>
        </form>
      )}

      {profiles.length === 0 ? (
        <div className="text-center py-20">
          <Bot className="w-10 h-10 text-cream-300 dark:text-ink-600 mx-auto mb-4" strokeWidth={1.5} />
          <h3 className="text-2xl font-display italic text-ink-900 dark:text-cream-100 mb-2">No models yet</h3>
          <p className="text-sm text-ink-400 dark:text-ink-300 font-body">Add a model and test the connection before it can be used.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {profiles.map((profile) => (
            <div key={profile.id} className="rounded-xl border border-ink-100/60 dark:border-ink-700/60 bg-white dark:bg-ink-800 p-4">
              <div className="flex items-start justify-between gap-3">
                <button onClick={() => openExisting(profile)} className="text-left">
                  <div className="font-body font-medium text-ink-900 dark:text-cream-100">{profile.name}</div>
                  <div className="text-xs text-ink-400 mt-1">
                    {profile.provider} · {profile.model_id} · {profile.context_window.toLocaleString()} tokens
                  </div>
                </button>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] uppercase tracking-wide font-semibold px-2 py-1 rounded ${
                    profile.usable
                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200'
                      : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200'
                  }`}>
                    {profile.status}
                  </span>
                  <button onClick={() => void handleDelete(profile.id)} title="Remove" className="text-ink-300 hover:text-status-error">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {profile.last_error && (
                <p className="mt-3 text-sm font-body text-status-error">{profile.last_error}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
