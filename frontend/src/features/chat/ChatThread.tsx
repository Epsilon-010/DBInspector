import { useEffect, useRef } from 'react'

import type { ChatTurn } from './types'
import { ChatTurnView } from './ChatTurn'

interface ChatThreadProps {
  turns: ChatTurn[]
}

export function ChatThread({ turns }: ChatThreadProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const lastTurn = turns[turns.length - 1]
  const lastStatus = lastTurn?.status

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns.length, lastStatus])

  if (turns.length === 0) return null

  return (
    <div className="space-y-8">
      {turns.map((turn, idx) => (
        <ChatTurnView key={turn.id} turn={turn} isLatest={idx === turns.length - 1} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
