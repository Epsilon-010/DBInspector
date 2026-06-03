import { graphqlRequest } from '@/api/client'
import { parseFinalReport, REPORT_GRAPHQL_FIELDS, type RawFinalReport } from '@/api/reportShape'
import type { Conversation } from '@/domain/types'

const START_CONVERSATION = /* GraphQL */ `
  mutation StartConversation {
    startConversation {
      id
    }
  }
`

interface StartConversationData {
  startConversation: { id: string }
}

export async function startConversation(): Promise<string> {
  const data = await graphqlRequest<StartConversationData>({
    query: START_CONVERSATION,
    operationName: 'StartConversation',
  })
  return data.startConversation.id
}

const CONVERSATION_QUERY = /* GraphQL */ `
  query Conversation($conversationId: ID!) {
    conversation(conversationId: $conversationId) {
      id
      createdAt
      updatedAt
      turns {
        createdAt
        report {
          ${REPORT_GRAPHQL_FIELDS}
        }
      }
    }
  }
`

interface ConversationData {
  conversation:
    | {
        id: string
        createdAt: string
        updatedAt: string
        turns: Array<{ createdAt: string; report: RawFinalReport }>
      }
    | null
}

export async function fetchConversation(conversationId: string): Promise<Conversation | null> {
  const data = await graphqlRequest<ConversationData, { conversationId: string }>({
    query: CONVERSATION_QUERY,
    variables: { conversationId },
    operationName: 'Conversation',
  })
  if (!data.conversation) return null
  return {
    id: data.conversation.id,
    createdAt: data.conversation.createdAt,
    updatedAt: data.conversation.updatedAt,
    turns: data.conversation.turns.map((t) => ({
      createdAt: t.createdAt,
      report: parseFinalReport(t.report),
    })),
  }
}
