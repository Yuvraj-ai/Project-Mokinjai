import { useRef, useState } from 'react'
import { Plus } from 'lucide-react'
import { fieldTypeLabel, type OutputField } from '../../api/structuredOutputs'

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

  return (
    <div className="rounded-lg border border-ink-100 dark:border-ink-700 bg-white dark:bg-ink-800 overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 bg-cream-100 dark:bg-ink-700/50 border-b border-cream-200 dark:border-ink-700">
        <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-400">Fields</span>
        <span className="text-[10px] text-ink-400">{fields.length}</span>
      </div>

      <div className="max-h-72 overflow-y-auto" data-testid="field-list">
        {fields.map((field, index) => {
          const isDropTarget = over === index && dragging !== null && dragging !== index
          return (
            <div key={index}>
              {isDropTarget && (
                <div className="mx-2 my-1 h-6 rounded border border-dashed border-accent-warm bg-accent-warm/5" />
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
                className={`flex items-center gap-2 px-2 py-1.5 border-b border-cream-100 dark:border-ink-700/60 cursor-pointer text-sm ${
                  selectedIndex === index
                    ? 'bg-cream-100 dark:bg-ink-700/60 shadow-[inset_2px_0_0_#C4956A]'
                    : 'hover:bg-cream-50 dark:hover:bg-ink-700/40'
                } ${dragging === index ? 'opacity-40' : ''}`}
              >
                <span
                  className="select-none rounded border border-ink-100 dark:border-ink-600 px-1 text-xs leading-4 font-mono text-accent-muted cursor-grab active:cursor-grabbing"
                  title="Press and hold to reorder"
                >
                  =
                </span>
                <span className="flex-1 truncate font-body text-ink-800 dark:text-cream-100">
                  {field.name || <span className="italic text-ink-300">untitled</span>}
                </span>
                <span className="rounded bg-ink-50 dark:bg-ink-700 px-1.5 py-0.5 text-[10px] text-ink-500 dark:text-ink-200 font-mono whitespace-nowrap">
                  {fieldTypeLabel(field)}
                </span>
              </div>
            </div>
          )
        })}
        {dragging !== null && over === fields.length - 1 && (
          <div className="mx-2 my-1 h-6 rounded border border-dashed border-accent-warm bg-accent-warm/5" />
        )}
      </div>

      <div className="p-2 border-t border-cream-200 dark:border-ink-700">
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex items-center gap-1.5 rounded-lg border border-ink-100 dark:border-ink-600 px-3 py-1.5 text-xs font-body text-ink-600 dark:text-cream-200 hover:bg-cream-100 dark:hover:bg-ink-700"
        >
          <Plus className="w-3.5 h-3.5" /> Add field
        </button>
      </div>
    </div>
  )
}
