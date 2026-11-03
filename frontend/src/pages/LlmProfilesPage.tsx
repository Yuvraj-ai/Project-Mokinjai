import { useEffect, useState } from 'react'
import { Plus, Trash2, Loader2 } from 'lucide-react'
import { listWorkspaces } from '../api/workspaces'
import {
  deleteLlmProfile,
  listLlmProfiles,
  lookupContextWindow,
  testLlmProfile,
  type LlmProfile,
  type LlmProvider,
} from '../api/llmProfiles'
import Button from '../components/ui/Button'
import { Spinner, EmptyState } from '../components/ui/Feedback'
import Badge from '../components/ui/Badge'

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
  max_output_tokens: '',
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
      max_output_tokens: profile.max_output_tokens ? String(profile.max_output_tokens) : '',
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
        max_output_tokens: form.max_output_tokens ? Number(form.max_output_tokens) : null,
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
      const detail = error &&
        typeof error === 'object' &&
        'response' in error &&
        error.response &&
        typeof error.response === 'object' &&
        'data' in error.response &&
        error.response.data &&
        typeof error.response.data === 'object' &&
        'detail' in error.response.data
        ? String(error.response.data.detail)
        : null
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
        <Spinner className="w-6 h-6" />
      </div>
    )
  }

  const windowLabel = knownWindow
    ? `Context window ${knownWindow.toLocaleString()} from the model profile`
    : 'Context window is required for this model id'

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-ink tracking-tight leading-tight">LLMs</h1>
          <p className="mt-1 text-sm text-ink-muted">
            A model can be used in agent creation only after a passing connection test.
          </p>
        </div>
        <Button onClick={openNew}>
          <Plus className="w-4 h-4" aria-hidden /> Add LLM
        </Button>
      </div>

      {showForm && (
        <form
          className="mb-8 rounded-xl border border-line bg-surface p-5 space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            void handleTest()
          }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-ink">Title</label>
              <input
                value={form.name}
                onChange={(event) => setField('name', event.target.value)}
                required
                className="w-full rounded-lg border border-line bg-surface h-9 px-3 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-ink">Provider</label>
              <select
                value={form.provider}
                onChange={(event) => {
                  const provider = event.target.value as LlmProvider
                  setField('provider', provider)
                  setKnownWindow(null)
                  void refreshWindow(provider, form.model_id)
                }}
                className="w-full rounded-lg border border-line bg-surface h-9 px-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {PROVIDERS.map((provider) => (
                  <option key={provider.value} value={provider.value}>{provider.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-ink">Model id</label>
              <input
                value={form.model_id}
                onChange={(event) => setField('model_id', event.target.value)}
                onBlur={() => void refreshWindow(form.provider, form.model_id)}
                required
                className="w-full rounded-lg border border-line bg-surface h-9 px-3 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-ink">
                API key {form.profile_id ? '(blank keeps the saved key)' : ''}
              </label>
              <input
                type="password"
                value={form.api_key}
                onChange={(event) => setField('api_key', event.target.value)}
                required={!form.profile_id}
                autoComplete="off"
                className="w-full rounded-lg border border-line bg-surface h-9 px-3 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            {form.provider === 'custom' && (
              <div className="sm:col-span-2">
                <label className="mb-1.5 block text-[13px] font-medium text-ink">Base URL</label>
                <input
                  value={form.base_url}
                  onChange={(event) => setField('base_url', event.target.value)}
                  required
                  placeholder="https://example.com/v1"
                  className="w-full rounded-lg border border-line bg-surface h-9 px-3 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            )}
            {knownWindow ? (
              <p className="col-span-2 mt-1 text-sm text-ink-muted">{windowLabel}</p>
            ) : (
              <div>
                <label className="mb-1.5 block text-[13px] font-medium text-ink">Context window</label>
                <input
                  type="number"
                  min={1}
                  value={form.context_window}
                  onChange={(event) => {
                    setField('context_window', event.target.value)
                    if (!form.compaction_at_tokens && event.target.value) {
                      setField('compaction_at_tokens', String(Math.floor(Number(event.target.value) * 0.8)))
                    }
                  }}
                  required
                  className="w-full rounded-lg border border-line bg-surface h-9 px-3 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            )}
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-ink">Compact after tokens</label>
              <input
                type="number"
                min={1}
                value={form.compaction_at_tokens}
                onChange={(event) => setField('compaction_at_tokens', event.target.value)}
                required
                className="w-full rounded-lg border border-line bg-surface h-9 px-3 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-ink">Max output tokens</label>
              <input
                type="number"
                min={1}
                value={form.max_output_tokens}
                onChange={(event) => setField('max_output_tokens', event.target.value)}
                placeholder="4096 (or the model card)"
                className="w-full rounded-lg border border-line bg-surface h-9 px-3 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <span className="mt-1 block text-xs text-ink-subtle">
                Caps the agent's Max completions. Blank uses the model card, then 4096.
              </span>
            </div>
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-ink">Input $ / 1M tokens</label>
              <input
                type="number"
                min={0}
                step="0.0001"
                value={form.input_price_per_million}
                onChange={(event) => setField('input_price_per_million', event.target.value)}
                required
                className="w-full rounded-lg border border-line bg-surface h-9 px-3 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-ink">Output $ / 1M tokens</label>
              <input
                type="number"
                min={0}
                step="0.0001"
                value={form.output_price_per_million}
                onChange={(event) => setField('output_price_per_million', event.target.value)}
                required
                className="w-full rounded-lg border border-line bg-surface h-9 px-3 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-ink">Cache $ / 1M tokens</label>
              <input
                type="number"
                min={0}
                step="0.0001"
                value={form.cache_price_per_million}
                onChange={(event) => setField('cache_price_per_million', event.target.value)}
                required
                className="w-full rounded-lg border border-line bg-surface h-9 px-3 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
          {formError && (
            <p className="text-sm text-status-error whitespace-pre-wrap">{formError}</p>
          )}
          <Button type="submit" disabled={testing} className="w-full sm:w-auto">
            {testing && <Loader2 className="w-3 h-3 animate-spin" aria-hidden />}
            {testing ? 'Verifying…' : 'Test connection'}
          </Button>
        </form>
      )}

      {profiles.length === 0 ? (
        <div className="bg-surface border border-line rounded-xl">
          <EmptyState
            title="No models yet"
            description="Add a model and test the connection before it can be used."
          />
        </div>
      ) : (
        <div className="space-y-3">
          {profiles.map((profile) => (
            <div key={profile.id} className="bg-surface rounded-xl border border-line p-4">
              <div className="flex items-start justify-between gap-3">
                <button onClick={() => openExisting(profile)} className="text-left">
                  <div className="text-sm font-medium text-ink">{profile.name}</div>
                  <div className="text-xs text-ink-muted mt-1">
                    {profile.provider} · {profile.model_id} · {profile.context_window.toLocaleString()} tokens
                    {profile.max_output_tokens ? ` · max ${profile.max_output_tokens.toLocaleString()} out` : ''}
                  </div>
                </button>
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    tone={profile.usable ? 'success' : 'danger'}
                  >
                    {profile.status}
                  </Badge>
                  <button onClick={() => void handleDelete(profile.id)} title="Remove" aria-label={`Remove ${profile.name}`}
                    className="rounded-md p-1.5 text-ink-subtle transition-colors hover:bg-status-error-soft hover:text-status-error">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {profile.last_error && (
                <p className="mt-3 text-[13px] text-status-error">{profile.last_error}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
