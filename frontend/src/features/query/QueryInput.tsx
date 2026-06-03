import { useState, type FormEvent } from 'react'

import { Button } from '@/components/Button'

const SUGGESTIONS = [
  '¿Cuáles son los 5 álbumes con más canciones?',
  '¿Qué países compraron más en 2024?',
  'Top 10 artistas por ventas totales',
  'Ventas mensuales del último año',
]

interface QueryInputProps {
  onSubmit: (question: string) => void
  loading: boolean
  showSuggestions?: boolean
}

export function QueryInput({ onSubmit, loading, showSuggestions = true }: QueryInputProps) {
  const [value, setValue] = useState('')

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || loading) return
    onSubmit(trimmed)
    setValue('')
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="relative">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={
            showSuggestions
              ? 'Pregunta sobre tus datos…  (ej. ¿Top 5 productos este año?)'
              : 'Sigue preguntando — el bot recuerda los turnos anteriores'
          }
          disabled={loading}
          className="w-full rounded-2xl border border-white/10 bg-bg-panel/80 backdrop-blur px-5 py-4 pr-32 text-ink placeholder:text-ink-faint focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/30 transition disabled:opacity-60"
        />
        <Button
          type="submit"
          loading={loading}
          disabled={!value.trim()}
          className="absolute right-2 top-1/2 -translate-y-1/2"
        >
          {loading ? 'Procesando' : 'Preguntar'}
        </Button>
      </form>
      {showSuggestions && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => !loading && setValue(s)}
              disabled={loading}
              className="rounded-full border border-white/5 bg-white/[0.02] px-3 py-1 text-xs text-ink-dim hover:border-accent/30 hover:text-ink transition disabled:opacity-40"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
