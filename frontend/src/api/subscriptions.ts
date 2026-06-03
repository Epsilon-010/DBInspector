import { createClient, type Client } from 'graphql-ws'

import { parseFinalReport, REPORT_GRAPHQL_FIELDS, type RawFinalReport } from '@/api/reportShape'
import type { PipelineEvent, PipelineStage } from '@/domain/types'
import { env } from '@/lib/env'

const PROGRESS_SUBSCRIPTION = /* GraphQL */ `
  subscription Progress($requestId: ID!) {
    progress(requestId: $requestId) {
      __typename
      ... on ProgressEventGQL {
        stage
        message
        attempt
        payloadJson
      }
      ... on RejectedEventGQL {
        reason
      }
      ... on FailedEventGQL {
        stage
        error
      }
      ... on ResultEventGQL {
        report {
          ${REPORT_GRAPHQL_FIELDS}
        }
      }
    }
  }
`

type RawEvent =
  | {
      __typename: 'ProgressEventGQL'
      stage: PipelineStage
      message: string
      attempt: number
      payloadJson: string
    }
  | { __typename: 'RejectedEventGQL'; reason: string }
  | { __typename: 'FailedEventGQL'; stage: string; error: string }
  | { __typename: 'ResultEventGQL'; report: RawFinalReport }

let _client: Client | null = null

function getClient(): Client {
  if (_client === null) {
    _client = createClient({
      url: env.wsUrl,
      lazy: true,
      retryAttempts: 3,
      shouldRetry: () => true,
    })
  }
  return _client
}

export interface SubscriptionHandle {
  unsubscribe: () => void
}

export function subscribeProgress(
  requestId: string,
  handlers: {
    onEvent: (evt: PipelineEvent) => void
    onError: (err: unknown) => void
    onComplete: () => void
  },
): SubscriptionHandle {
  const client = getClient()
  const unsubscribe = client.subscribe<{ progress: RawEvent }>(
    {
      query: PROGRESS_SUBSCRIPTION,
      variables: { requestId },
      operationName: 'Progress',
    },
    {
      next: (payload: { data?: { progress: RawEvent } | null }) => {
        if (!payload.data) return
        const mapped = mapRawEvent(payload.data.progress)
        if (mapped) handlers.onEvent(mapped)
      },
      error: handlers.onError,
      complete: handlers.onComplete,
    },
  )
  return { unsubscribe }
}

function mapRawEvent(raw: RawEvent): PipelineEvent | null {
  switch (raw.__typename) {
    case 'ProgressEventGQL':
      return {
        kind: 'progress',
        stage: raw.stage,
        message: raw.message,
        attempt: raw.attempt,
        payload: safeParseJson(raw.payloadJson),
      }
    case 'RejectedEventGQL':
      return { kind: 'rejected', reason: raw.reason }
    case 'FailedEventGQL':
      return { kind: 'failed', stage: raw.stage, error: raw.error }
    case 'ResultEventGQL':
      return { kind: 'result', report: parseFinalReport(raw.report) }
    default:
      return null
  }
}

function safeParseJson(text: string): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(text || '{}')
    return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}
