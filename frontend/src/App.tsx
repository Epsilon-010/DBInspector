import { useMemo } from 'react'

import { Button } from '@/components/Button'
import { ChatThread, useChat } from '@/features/chat'
import { QueryInput } from '@/features/query'
import {
  readConversationIdFromUrl,
  writeConversationIdToUrl,
} from '@/lib/conversationUrl'

function App() {
  const initialConversationId = useMemo(() => readConversationIdFromUrl(), [])

  const { turns, isStreaming, isHydrating, conversationId, submit, reset } = useChat({
    initialConversationId,
    onConversationIdChange: writeConversationIdToUrl,
  })
  const hasHistory = turns.length > 0

  return (
    <div className="min-h-full flex flex-col">
      <div className="mx-auto w-full max-w-4xl px-4 pt-10 md:pt-16 pb-44 flex-1 space-y-8">
        <header className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="grid place-items-center h-9 w-9 rounded-xl bg-gradient-to-br from-accent to-accent-soft text-white font-bold shadow-lg shadow-accent/30">
              DB
            </span>
            <div>
              <h1 className="text-xl font-semibold text-ink tracking-tight">DBInspector</h1>
              <p className="text-xs text-ink-faint">
                Chat con tus datos · SQL seguro · resumen + gráfica en cada turno
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {conversationId && (
              <code className="hidden md:inline rounded-md bg-bg-panel/60 border border-white/5 px-2 py-1 text-[10px] text-ink-faint font-mono">
                conv: {conversationId.slice(0, 8)}…
              </code>
            )}
            {hasHistory && (
              <Button variant="ghost" onClick={reset} disabled={isStreaming}>
                Nueva conversación
              </Button>
            )}
          </div>
        </header>

        {isHydrating ? (
          <p className="text-sm text-ink-dim animate-pulse-soft">Recuperando conversación…</p>
        ) : (
          <ChatThread turns={turns} />
        )}
      </div>

      <div className="sticky bottom-0 bg-gradient-to-t from-bg via-bg/95 to-transparent pt-6 pb-6">
        <div className="mx-auto max-w-4xl px-4 space-y-3">
          <QueryInput
            onSubmit={submit}
            loading={isStreaming}
            showSuggestions={!hasHistory}
          />
          <p className="text-center text-xs text-ink-faint">
            DBInspector — backend hexagonal · PostgreSQL read-only
          </p>
        </div>
      </div>
    </div>
  )
}

export default App
