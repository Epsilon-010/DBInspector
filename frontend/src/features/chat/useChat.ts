import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchConversation, startConversation } from '@/api/chat'
import { toErrorMessage } from '@/api/client'
import { runQuery } from '@/api/mutations'
import { subscribeProgress, type SubscriptionHandle } from '@/api/subscriptions'
import type { PipelineEvent } from '@/domain/types'

import type { ChatTurn } from './types'

export interface UseChatOptions {
  initialConversationId?: string | null
  onConversationIdChange?: (id: string | null) => void
}

export interface Chat {
  turns: ChatTurn[]
  isStreaming: boolean
  isHydrating: boolean
  conversationId: string | null
  submit: (question: string) => Promise<void>
  reset: () => void
}

export function useChat(options: UseChatOptions = {}): Chat {
  const { initialConversationId = null, onConversationIdChange } = options

  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [conversationId, setConversationIdState] = useState<string | null>(initialConversationId)
  const [isStreaming, setIsStreaming] = useState(false)
  const [isHydrating, setIsHydrating] = useState(Boolean(initialConversationId))

  const subscriptionRef = useRef<SubscriptionHandle | null>(null)
  const conversationIdRef = useRef<string | null>(initialConversationId)
  const isStreamingRef = useRef(false)
  const generationRef = useRef(0)
  const onChangeRef = useRef(onConversationIdChange)
  useEffect(() => {
    onChangeRef.current = onConversationIdChange
  })

  const setConversationId = useCallback((id: string | null) => {
    if (conversationIdRef.current === id) return
    conversationIdRef.current = id
    setConversationIdState(id)
    onChangeRef.current?.(id)
  }, [])

  const cleanupSubscription = useCallback(() => {
    if (subscriptionRef.current) {
      subscriptionRef.current.unsubscribe()
      subscriptionRef.current = null
    }
  }, [])

  useEffect(() => cleanupSubscription, [cleanupSubscription])

  // Confirmed-null (server says conversation is gone) clears state + URL.
  // Exception (network blip) leaves the URL alone so a refresh can retry.
  useEffect(() => {
    if (!initialConversationId) return
    let cancelled = false
    void (async () => {
      try {
        const conversation = await fetchConversation(initialConversationId)
        if (cancelled) return
        if (conversation === null) {
          setConversationId(null)
          setTurns([])
        } else {
          setTurns(conversation.turns.map(restoredTurn))
        }
      } catch {
        if (cancelled) return
        conversationIdRef.current = null
        setConversationIdState(null)
        setTurns([])
      } finally {
        if (!cancelled) setIsHydrating(false)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const reset = useCallback(() => {
    generationRef.current += 1
    cleanupSubscription()
    setTurns([])
    setConversationId(null)
    setIsStreaming(false)
    isStreamingRef.current = false
  }, [cleanupSubscription, setConversationId])

  const submit = useCallback(
    async (question: string) => {
      const trimmed = question.trim()
      if (!trimmed || isStreamingRef.current) return
      isStreamingRef.current = true
      setIsStreaming(true)

      const generation = generationRef.current
      const isCurrent = () => generationRef.current === generation

      let cid = conversationIdRef.current
      if (cid === null) {
        try {
          cid = await startConversation()
        } catch (err) {
          if (isCurrent()) {
            appendFailureTurn(setTurns, trimmed, 'mutation', toErrorMessage(err))
            isStreamingRef.current = false
            setIsStreaming(false)
          }
          return
        }
        if (!isCurrent()) return
        setConversationId(cid)
      }

      const turnId = createTurnId()
      setTurns((prev) => [
        ...prev,
        { id: turnId, question: trimmed, status: 'streaming', progress: [] },
      ])

      let requestId: string
      try {
        requestId = await runQuery({ question: trimmed, conversationId: cid })
      } catch (err) {
        if (isCurrent()) {
          finalizeTurnFailure(setTurns, turnId, 'mutation', toErrorMessage(err))
          isStreamingRef.current = false
          setIsStreaming(false)
        }
        return
      }
      if (!isCurrent()) return

      cleanupSubscription()
      subscriptionRef.current = subscribeProgress(requestId, {
        onEvent: (evt) => {
          if (!isCurrent()) return
          applyEventToTurn(setTurns, turnId, evt)
        },
        onError: (err) => {
          if (!isCurrent()) return
          finalizeTurnFailure(setTurns, turnId, 'subscription', toErrorMessage(err))
          isStreamingRef.current = false
          setIsStreaming(false)
          cleanupSubscription()
        },
        onComplete: () => {
          if (!isCurrent()) return
          isStreamingRef.current = false
          setIsStreaming(false)
          cleanupSubscription()
        },
      })
    },
    [cleanupSubscription, setConversationId],
  )

  return { turns, isStreaming, isHydrating, conversationId, submit, reset }
}

function createTurnId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `turn-${Math.random().toString(36).slice(2)}-${Date.now()}`
}

type TurnSetter = (updater: (prev: ChatTurn[]) => ChatTurn[]) => void

function updateTurn(setTurns: TurnSetter, turnId: string, patch: (t: ChatTurn) => ChatTurn): void {
  setTurns((prev) => prev.map((t) => (t.id === turnId ? patch(t) : t)))
}

function applyEventToTurn(setTurns: TurnSetter, turnId: string, evt: PipelineEvent): void {
  switch (evt.kind) {
    case 'progress':
      updateTurn(setTurns, turnId, (turn) => ({
        ...turn,
        latestStage: evt.stage,
        progress: [...turn.progress, evt],
      }))
      return
    case 'rejected':
      updateTurn(setTurns, turnId, (turn) => ({
        ...turn,
        status: 'rejected',
        rejection: evt.reason,
      }))
      return
    case 'failed':
      updateTurn(setTurns, turnId, (turn) => ({
        ...turn,
        status: 'failed',
        error: { stage: evt.stage, message: evt.error },
      }))
      return
    case 'result':
      updateTurn(setTurns, turnId, (turn) => ({
        ...turn,
        status: 'done',
        report: evt.report,
      }))
      return
  }
}

function finalizeTurnFailure(
  setTurns: TurnSetter,
  turnId: string,
  stage: string,
  message: string,
): void {
  updateTurn(setTurns, turnId, (turn) => ({
    ...turn,
    status: 'failed',
    error: { stage, message },
  }))
}

function appendFailureTurn(
  setTurns: TurnSetter,
  question: string,
  stage: string,
  message: string,
): void {
  setTurns((prev) => [
    ...prev,
    {
      id: createTurnId(),
      question,
      status: 'failed',
      progress: [],
      error: { stage, message },
    },
  ])
}

function restoredTurn(turn: { report: ChatTurn['report']; createdAt: string }): ChatTurn {
  const report = turn.report!
  return {
    id: createTurnId(),
    question: report.question,
    status: 'done',
    progress: [],
    report,
  }
}
