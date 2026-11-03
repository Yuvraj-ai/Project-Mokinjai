import { useRef, useState } from 'react'
import { Plus } from 'lucide-react'
import { fieldTypeLabel, type OutputField } from '../../api/structuredOutputs'
import { cn } from '../../lib/utils'

interface Props {
  fields: OutputField[]
  selectedIndex: number | null
  onSelect: (index: number) => void
  onReorder: (from: number, to: number) => void
  onAdd: () => void
}

/**
 * The ordered field list. Order is meaningful — it becomes the property order
 * of the compiled schema — so rows are dragged into place with the grip.
 */
export default function FieldList({ fields, selectedIndex, onSelect, onReorder, onAdd }: Props) {
  const [dragging, setDragging] = useState<number | null>(null)
  const [over, setOver] = useState<number | null>(null)
  const armed = useRef<number | null>(null)

  const drop = (target: number) => {
    if (dragging !== null && dragging !== target) onReorder(dragging, target)
    setDragging(null)
    setOver(null)
    armed.current = null
  }

  const headerClass = cn('flex items-center justify-between px-3 py-2 border-b border-line',
    fields.length === 0 ? 'bg-surface-muted' : 'bg-surface-muted')
  const rowClass = (index: number) => cn(
    'flex items-center gap-2 px-2 py-1.5 border-b border-line cursor-pointer text-sm transition-colors duration-150',
    selectedIndex === index ? 'bg-surface-muted shadow-[inset_2px_0_0_var(--primary)]' : 'hover:bg-surface-muted',
    dragging === index ? 'opacity-40' : '',
  )

  return (
    <div className="rounded-lg border border-line overflow-hidden flex flex-col">
      <div className={cn(headerClass)}>
        <span className="text-[13px] font-medium text-ink">Fields</span>
        <span className="font-mono text-xs text-ink-subtle">{fields.length}</span>
      </div>

      <div className="max-h-72 overflow-y-auto" data-testid="field-list">
        {fields.map((field: OutputField, index: number) => {
          const isDropTarget = over === index && dragging !== null && dragging !== index
          return (
            <div key={index}>
              {isDropTarget && (
                <div className="mx-2 my-1 h-6 rounded border border-dashed border-line-strong bg-surface-muted" />
              )}
              <div
                draggable
                onMouseDown={() => {
                  armed.current = index
                }}
                onDragStart={(event) => {
                  if (armed.current !== index) {
                    event.preventDefault()
                    return
                  }
                  setDragging(index)
                  event.dataTransfer.effectAllowed = 'move'
                }}
                onDragOver={(event) => {
                  event.preventDefault()
                  setOver(index)
                }}
                onDrop={(event) => {
                  event.preventDefault()
                  drop(index)
                }}
                onDragEnd={() => {
                  setDragging(null)
                  setOver(null)
                  armed.current = null
                }}
                onClick={() => onSelect(index)}
                className={rowClass(index)}
              >
                <span
                  className="select-none rounded border border-line-strong px-1 text-xs leading-4 font-mono text-ink-subtle cursor-grab active:cursor-grabbing"
                  title="Press and hold to reorder"
                >
                  =
                </span>
                <span className="flex-1 truncate text-ink">
                  {field.name || <span className="italic text-ink-subtle">untitled</span>}
                </span>
                <span className="rounded-md border border-line bg-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-ink-muted whitespace-nowrap">
                  {fieldTypeLabel(field)}
                </span>
              </div>
            </div>
          )
        })}
        {dragging !== null && over === fields.length - 1 && (
          <div className="mx-2 my-1 h-6 rounded border border-dashed border-line-strong bg-surface-muted" />
        )}
      </div>

      <div className="p-2 border-t border-line">
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-xs text-ink muted transition-colors hover:bg-surface-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <Plus className="w-3.5 h-3.5" aria-hidden /> Add field
        </button>
      </div>
    </div>
  )
}
