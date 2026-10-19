import { useEffect, useState } from 'react'

interface NumberSliderProps {
  label: string
  value: number
  min: number
  max: number
  step?: number
  hint?: string
  disabled?: boolean
  onChange: (value: number) => void
}

/**
 * One value, two controls. The input allows typing (and clamps on the way out),
 * the range drives the same state, so they can never disagree.
 */
export default function NumberSlider({
  label,
  value,
  min,
  max,
  step = 1,
  hint,
  disabled,
  onChange,
}: NumberSliderProps) {
  const [text, setText] = useState(String(value))

  useEffect(() => {
    setText(String(value))
  }, [value])

  const clamp = (raw: number) => Math.min(max, Math.max(min, raw))

  return (
    <label className="block">
      <span className="mb-1 flex items-center justify-between gap-2">
        <span className="text-[10px] uppercase tracking-wider font-semibold text-ink-400">
          {label}
        </span>
        <input
          type="number"
          value={text}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          onChange={(event) => {
            const raw = event.target.value
            setText(raw)
            const parsed = Number(raw)
            if (raw.trim() !== '' && Number.isFinite(parsed)) onChange(clamp(parsed))
          }}
          onBlur={() => setText(String(clamp(Number(text) || min)))}
          className="w-20 rounded-md border border-ink-100 dark:border-ink-600 bg-cream-50 dark:bg-ink-700/50 px-2 py-1 text-right font-mono text-xs text-ink-800 dark:text-cream-100 disabled:opacity-40"
        />
      </span>
      <input
        type="range"
        value={value}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        onChange={(event) => onChange(clamp(Number(event.target.value)))}
        className="w-full accent-[#C4956A] disabled:opacity-40"
      />
      {hint && <span className="mt-1 block text-[10px] text-ink-400">{hint}</span>}
    </label>
  )
}
