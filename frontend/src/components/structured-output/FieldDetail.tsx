import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { fieldTypeLabel, ITEM_TYPES, SCALAR_TYPES, type ItemType, type OutputField } from '../../api/structuredOutputs'
import { Input, Select } from '../ui/Field'

const labelClass = 'mb-1.5 block text-[13px] font-medium text-ink'

interface Props {
  field: OutputField
  /** Names of the workspace's other definitions, for the @ picker. */
  definitions: { name: string; fieldCount: number }[]
  onChange: (patch: Partial<OutputField>) => void
  onRemove: () => void
}

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
  const suggestions = definitions.filter((definition: { name: string; fieldCount: number }) => definition.name.toLowerCase().includes(query))
  const refValue = field.type === 'reference' ? field.ref : field.items_ref

  return (
    <div className="rounded-lg border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <span className="text-[13px] font-medium text-ink">
          {field.name || 'New field'}
        </span>
        <div className="flex items-center gap-3">
          <span className="rounded-md border border-line bg-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
            {fieldTypeLabel(field)}
          </span>
          <button type="button" onClick={onRemove} title="Remove field" className="rounded-md p-1 text-ink-subtle transition-colors hover:bg-status-error-soft hover:text-status-error">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="p-4 space-y-4">
        <div className="flex gap-3">
          <label className="flex-1">
            <span className={labelClass}>Name</span>
            <Input
              value={field.name}
              onChange={(event) => onChange({ name: event.target.value })}
              placeholder="answer"
              className="font-mono"
            />
          </label>
          <label className="flex-1">
            <span className={labelClass}>Type</span>
            <Select
              value={field.type}
              onChange={(event) => changeType(event.target.value as OutputField['type'])}
            >
              {SCALAR_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
              <option value="list">list</option>
              <option value="reference">reference</option>
            </Select>
          </label>
          <label className="flex items-center gap-2 pt-5 cursor-pointer">
            <input
              type="checkbox"
              checked={field.required}
              onChange={(event) => onChange({ required: event.target.checked })}
              className="accent-primary"
            />
            <span className="text-[13px] text-ink-muted">required</span>
          </label>
        </div>

        <label className="block">
          <span className={labelClass}>Description</span>
          <textarea
            value={field.description}
            onChange={(event) => onChange({ description: event.target.value })}
            rows={3}
            placeholder="What the model should put in this field. This is the instruction it gets."
            className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-ink placeholder:text-ink-subtle resize-y focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>

        {(field.type === 'list' || field.type === 'reference') && (
          <div className="border-t border-line pt-4 space-y-4">
            {field.type === 'list' && (
              <label className="block">
                <span className={labelClass}>items</span>
                <Select
                  value={field.items_type ?? 'string'}
                  onChange={(event) => changeItemsType(event.target.value as ItemType)}
                  className="max-w-[180px]"
                >
                  {ITEM_TYPES.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </Select>
              </label>
            )}

            {(field.type === 'reference' || field.items_type === 'reference') && (
              <div className="relative">
                <span className={labelClass}>
                  {field.type === 'reference' ? 'reference' : 'items → reference'}
                </span>
                <Input
                  value={refValue ?? ''}
                  onChange={(event) => {
                    setRefQuery(event.target.value)
                    const next = event.target.value.replace(/^@/, '')
                    onChange(field.type === 'reference' ? { ref: next } : { items_ref: next })
                  }}
                  onFocus={() => setRefQuery(refValue ?? '')}
                  onBlur={() => setRefQuery(null)}
                  placeholder="@Step"
                  className="font-mono max-w-[240px]"
                />
                {refQuery !== null && suggestions.length > 0 && (
                  <div className="absolute z-30 mt-1 w-[240px] rounded-xl border border-line bg-surface-raised shadow-menu overflow-hidden">
                    <div className="px-3 py-1.5 text-[11px] uppercase tracking-wide text-ink-subtle bg-surface-muted">
                      Saved outputs
                    </div>
                    {suggestions.map((definition: { name: string; fieldCount: number }) => (
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
                        className="flex w-full items-center justify-between px-3 py-2 text-left text-[13px] transition-colors hover:bg-surface-muted"
                      >
                        <span className="font-mono text-ink">@{definition.name}</span>
                        <span className="text-[11px] text-ink-subtle">{definition.fieldCount} fields</span>
                      </button>
                    ))}
                  </div>
                )}
                {definitions.length === 0 && (
                  <p className="mt-1 text-xs text-ink-subtle">
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
