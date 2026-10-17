import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { fieldTypeLabel, ITEM_TYPES, SCALAR_TYPES, type ItemType, type OutputField } from '../../api/structuredOutputs'

interface Props {
  field: OutputField
  /** Names of the workspace's other definitions, for the @ picker. */
  definitions: { name: string; fieldCount: number }[]
  onChange: (patch: Partial<OutputField>) => void
  onRemove: () => void
}

const inputClass =
  'w-full rounded-lg border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2.5 py-1.5 text-sm text-ink-800 dark:text-cream-100 font-body'

const labelClass = 'block text-[10px] uppercase tracking-wider font-semibold text-ink-400 mb-1'

export default function FieldDetail({ field, definitions, onChange, onRemove }: Props) {
  const [refQuery, setRefQuery] = useState<string | null>(null)

  const changeType = (type: OutputField['type']) => {
    // Drop the keys that only belonged to the previous type.
    const patch: Partial<OutputField> = {
      type,
      items_type: null,
      items_ref: null,
      ref: null,
    }
    if (type === 'list') patch.items_type = 'string'
    if (type === 'reference') patch.ref = definitions[0]?.name ?? ''
    onChange(patch)
  }

  const changeItemsType = (itemsType: ItemType) => {
    onChange({ items_type: itemsType, items_ref: itemsType === 'reference' ? definitions[0]?.name ?? '' : null })
  }

  const query = (refQuery ?? '').replace(/^@/, '').toLowerCase()
  const suggestions = definitions.filter((definition) => definition.name.toLowerCase().includes(query))
  const refValue = field.type === 'reference' ? field.ref : field.items_ref

  return (
    <div className="rounded-lg border border-ink-100 dark:border-ink-700 bg-white dark:bg-ink-800">
      <div className="flex items-center justify-between px-3 py-2 bg-cream-100 dark:bg-ink-700/50 border-b border-cream-200 dark:border-ink-700">
        <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-400">
          {field.name || 'New field'}
        </span>
        <div className="flex items-center gap-3">
          <span className="rounded bg-ink-50 dark:bg-ink-700 px-1.5 py-0.5 text-[10px] text-ink-500 dark:text-ink-200 font-mono">
            {fieldTypeLabel(field)}
          </span>
          <button type="button" onClick={onRemove} title="Remove field" className="text-ink-300 hover:text-status-error">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="p-3 space-y-3">
        <div className="flex gap-3">
          <label className="flex-1">
            <span className={labelClass}>Name</span>
            <input
              value={field.name}
              onChange={(event) => onChange({ name: event.target.value })}
              placeholder="answer"
              className={`${inputClass} font-mono`}
            />
          </label>
          <label className="flex-1">
            <span className={labelClass}>Type</span>
            <select
              value={field.type}
              onChange={(event) => changeType(event.target.value as OutputField['type'])}
              className={inputClass}
            >
              {SCALAR_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
              <option value="list">list</option>
              <option value="reference">reference</option>
            </select>
          </label>
          <label className="flex items-center gap-2 pt-4 cursor-pointer">
            <input
              type="checkbox"
              checked={field.required}
              onChange={(event) => onChange({ required: event.target.checked })}
              className="accent-accent-warm"
            />
            <span className="text-xs font-body text-ink-500 dark:text-ink-200">required</span>
          </label>
        </div>

        <label className="block">
          <span className={labelClass}>Description</span>
          <textarea
            value={field.description}
            onChange={(event) => onChange({ description: event.target.value })}
            rows={3}
            placeholder="What the model should put in this field. This is the instruction it gets."
            className={`${inputClass} resize-y`}
          />
        </label>

        {(field.type === 'list' || field.type === 'reference') && (
          <div className="border-t border-dashed border-cream-300 dark:border-ink-600 pt-3 space-y-3">
            {field.type === 'list' && (
              <label className="block">
                <span className={labelClass}>items</span>
                <select
                  value={field.items_type ?? 'string'}
                  onChange={(event) => changeItemsType(event.target.value as ItemType)}
                  className={`${inputClass} max-w-[180px]`}
                >
                  {ITEM_TYPES.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </label>
            )}

            {(field.type === 'reference' || field.items_type === 'reference') && (
              <div className="relative">
                <span className={labelClass}>
                  {field.type === 'reference' ? 'reference' : 'items → reference'}
                </span>
                <input
                  value={refValue ?? ''}
                  onChange={(event) => {
                    setRefQuery(event.target.value)
                    const next = event.target.value.replace(/^@/, '')
                    onChange(field.type === 'reference' ? { ref: next } : { items_ref: next })
                  }}
                  onFocus={() => setRefQuery(refValue ?? '')}
                  onBlur={() => setRefQuery(null)}
                  placeholder="@Step"
                  className={`${inputClass} font-mono max-w-[240px]`}
                />
                {refQuery !== null && suggestions.length > 0 && (
                  <div className="absolute z-10 mt-1 w-[240px] rounded-lg border border-ink-100 dark:border-ink-600 bg-white dark:bg-ink-800 shadow-lg overflow-hidden">
                    <div className="px-2 py-1 text-[9px] uppercase tracking-wider text-ink-400 bg-cream-100 dark:bg-ink-700/60">
                      Saved outputs
                    </div>
                    {suggestions.map((definition) => (
                      <button
                        key={definition.name}
                        type="button"
                        onMouseDown={(event) => {
                          event.preventDefault()
                          onChange(
                            field.type === 'reference'
                              ? { ref: definition.name }
                              : { items_ref: definition.name }
                          )
                          setRefQuery(null)
                        }}
                        className="flex w-full items-center justify-between px-2 py-1.5 text-left text-xs font-body hover:bg-cream-100 dark:hover:bg-ink-700/60"
                      >
                        <span className="font-mono text-ink-800 dark:text-cream-100">@{definition.name}</span>
                        <span className="text-[10px] text-ink-400">{definition.fieldCount} fields</span>
                      </button>
                    ))}
                  </div>
                )}
                {definitions.length === 0 && (
                  <p className="mt-1 text-[11px] font-body text-ink-400">
                    No other outputs yet. Save one first, then reference it here.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
